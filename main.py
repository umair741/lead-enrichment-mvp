import os
import json
import cleaner
import scorer
import config
from sheets_client import SheetsClient
from enricher import LeadEnricher

# Country name → ISO 3166-1 alpha-2 code mapping for phone parsing
COUNTRY_TO_ISO = {
    "france": "FR",
    "germany": "DE",
    "spain": "ES",
    "italy": "IT",
    "united kingdom": "GB",
    "uk": "GB",
    "united states": "US",
    "usa": "US",
    "canada": "CA",
    "belgium": "BE",
    "netherlands": "NL",
    "switzerland": "CH",
    "portugal": "PT",
    "poland": "PL",
    "austria": "AT",
}


def country_to_iso(country_name):
    """Converts a country name string to an ISO phone country code.
    Falls back to the config default (FR) if not recognized.
    """
    if not country_name:
        return config.DEFAULT_PHONE_COUNTRY
    return COUNTRY_TO_ISO.get(country_name.strip().lower(), config.DEFAULT_PHONE_COUNTRY)


def run_lead_pipeline():
    print("\n=============================================")
    print("      Lead Enrichment Pipeline Start         ")
    print("=============================================\n")

    # 1. Initialize Sheets connection
    sheets = SheetsClient()

    # 2. Read leads from sheet
    leads = sheets.read_leads()

    if not leads:
        print("[Error] No leads found in Google Sheets and no fallback data available.")
        print("        → Make sure your sheet has data, or check GOOGLE_SHEET_ID in your .env file.")
        print("        → If the sheet was empty, sample data should have been seeded automatically.")
        print("        → Re-run the script once the sheet has been populated.\n")
        return

    print(f"Loaded {len(leads)} raw company rows.")

    # 3. Clean & Deduplicate
    unique_leads = cleaner.deduplicate_leads(leads)
    print(f"After deduplication: {len(unique_leads)} unique companies.\n")

    # 4. Enrich each company
    enricher = LeadEnricher()
    enriched_records = []

    for idx, lead in enumerate(unique_leads, 1):
        company = cleaner.clean_company_name(lead.get("Company Name", ""))
        website = lead.get("Official Website", "")
        sector = lead.get("Sector", "")
        country = lead.get("Country", "")
        phone_country_code = country_to_iso(country)

        if not company and website:
            company = website.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]

        print(f"\n--- [{idx}/{len(unique_leads)}] {company} ---")

        enriched_row = {
            "Company Name": company,
            "Sector": sector,
            "Country": country,
            "Official Website": website,
            "Email": lead.get("Email", ""),
            "Phone": lead.get("Phone", ""),
            "LinkedIn Company Page": lead.get("LinkedIn Company Page", ""),
            "Source URL": lead.get("Source URL", ""),
            "Confidence Score": lead.get("Confidence Score", 0),
            "Status/Error": lead.get("Status/Error", "Pending"),
        }

        # Skip if already enriched
        if website and (enriched_row["Email"] or enriched_row["Phone"] or enriched_row["LinkedIn Company Page"]):
            print("  [Info] Lead already enriched. Skipping...")
            enriched_records.append(enriched_row)
            continue

        try:
            data = enricher.enrich_company(company, existing_website=website)

            enriched_row.update({
                "Official Website": data.get("website", "") or website,
                # Pass the lead's actual country code for correct phone validation
                "Phone": cleaner.clean_phone(data.get("phone", ""), country_code=phone_country_code),
                "Email": cleaner.clean_email(data.get("email", "")),
                "LinkedIn Company Page": data.get("linkedin", ""),
                "Source URL": data.get("source_url", ""),
            })

            scores = scorer.score_lead(enriched_row)
            enriched_row["Confidence Score"] = scores["quality_score"]
            enriched_row["Status/Error"] = scores["status"]

        except Exception as e:
            print(f"  [Error] Failed: {e}")
            enriched_row["Status/Error"] = f"Error: {e}"

        enriched_records.append(enriched_row)

    # 5. Save local JSON backup
    try:
        with open(config.OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(enriched_records, f, indent=4, ensure_ascii=False)
        print(f"\n[Backup] Saved to: {os.path.abspath(config.OUTPUT_JSON_PATH)}")
    except Exception as e:
        print(f"\n[Warning] Could not save local backup: {e}")

    # 6. Write back to Google Sheets
    sheets.write_back(enriched_records)

    # 7. Print summary
    print("\n=============================================")
    print("               RESULTS SUMMARY               ")
    print("=============================================")
    for rec in enriched_records:
        score = rec.get("Confidence Score", 0)
        status = rec.get("Status/Error", "Unknown")
        print(f"  {rec['Company Name']:25s} | Score: {score:3} | {status}")
    print("=============================================\n")


if __name__ == "__main__":
    run_lead_pipeline()