import os
import json
import cleaner
import scorer
from sheets_client import SheetsClient
from enricher import LeadEnricher


def run_lead_pipeline():
    print("\n=============================================")
    print("      Lead Enrichment Pipeline Start         ")
    print("=============================================\n")

    # 1. Initialize Sheets connection
    sheets = SheetsClient()

    # 2. Read leads from sheet
    leads = sheets.read_leads()
    is_fallback = False

    if not leads:
        print("[Info] No leads found on Google Sheets.")
        print("Using local mock data for testing...\n")
        leads = [
            {"Company": "Google LLC"},
            {"Company": "Microsoft"},
            {"Company": "Apple Inc."},
            {"Company": "GitHub"}
        ]
        is_fallback = True

    print(f"Loaded {len(leads)} raw company rows.")

    # 3. Clean & Deduplicate lead records
    unique_leads = cleaner.deduplicate_leads(leads)
    print(f"After deduplication: {len(unique_leads)} unique companies.\n")

    # 4. Enrich each company
    enricher = LeadEnricher()
    enriched_records = []

    for idx, lead in enumerate(unique_leads, 1):
        company = cleaner.clean_company_name(lead.get("Company", ""))
        website = lead.get("Website", "")
        
        # Fallback name if company name is missing but website is present
        if not company and website:
            company = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

        print(f"\n--- [{idx}/{len(unique_leads)}] {company} ---")

        # Base record structure
        enriched_row = {
            "Company": company,
            "Website": website,
            "Phone": lead.get("Phone", ""),
            "Email": lead.get("Email", ""),
            "LinkedIn": lead.get("LinkedIn", ""),
            "Source URL": lead.get("Source URL", ""),
            "Status": lead.get("Status", "Pending"),
            "Quality Score": lead.get("Quality Score", 0)
        }

        # Skip if already enriched
        if website and (enriched_row["Email"] or enriched_row["Phone"] or enriched_row["LinkedIn"]):
            print("  [Info] Lead already enriched. Skipping...")
            enriched_records.append(enriched_row)
            continue

        try:
            # Scrape website details
            data = enricher.enrich_company(company, existing_website=website)

            # Assign and score
            enriched_row.update({
                "Website": data.get("website", "") or website,
                "Phone": cleaner.clean_phone(data.get("phone", "")),
                "Email": cleaner.clean_email(data.get("email", "")),
                "LinkedIn": data.get("linkedin", ""),
                "Source URL": data.get("source_url", "")
            })
            
            scores = scorer.score_lead(enriched_row)
            enriched_row.update({"Quality Score": scores["quality_score"], "Status": scores["status"]})

        except Exception as e:
            print(f"  [Error] Failed: {e}")
            enriched_row["Status"] = "Needs Review"

        enriched_records.append(enriched_row)

    # 5. Always save local JSON backup first
    try:
        with open("enriched_leads_output.json", "w", encoding="utf-8") as f:
            json.dump(enriched_records, f, indent=4, ensure_ascii=False)
        print(f"\n[Backup] Saved to: {os.path.abspath('enriched_leads_output.json')}")
    except Exception as e:
        print(f"\n[Warning] Could not save local backup: {e}")

    # 6. Write results back to Google Sheets
    sheets.write_back(enriched_records)

    # 7. Print summary
    print("\n=============================================")
    print("               RESULTS SUMMARY               ")
    print("=============================================")
    for rec in enriched_records:
        score = rec.get("Quality Score", 0)
        status = rec.get("Status", "Unknown")
        print(f"  {rec['Company']:25s} | Score: {score:3} | {status}")
    print("=============================================\n")


if __name__ == "__main__":
    run_lead_pipeline()
