import json
import os
import gspread
from google.oauth2.service_account import Credentials
import config

# Column headers for the Google Sheet
HEADERS = [
    "Company Name", "Sector", "Country", "Official Website",
    "Email", "Phone", "LinkedIn Company Page", "Source URL",
    "Confidence Score", "Status/Error"
]


def _load_default_samples():
    """Loads sample leads from sample_leads.json if it exists."""
    sample_path = os.path.join(os.path.dirname(__file__), "sample_leads.json")
    if os.path.exists(sample_path):
        try:
            with open(sample_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Warning] Could not load sample_leads.json: {e}")
    return []


class SheetsClient:
    def __init__(self):
        self.client = None
        self.sheet = None
        self._authenticate()

    def _authenticate(self):
        if not os.path.exists(config.CREDENTIALS_PATH):
            print(f"[Warning] Credentials file not found at: {config.CREDENTIALS_PATH}")
            return

        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = Credentials.from_service_account_file(config.CREDENTIALS_PATH, scopes=scopes)
            self.client = gspread.authorize(creds)

            if config.SHEET_ID:
                self.sheet = self.client.open_by_key(config.SHEET_ID).worksheet(config.SHEET_NAME)
                print(f"Successfully connected to Google Sheet: {config.SHEET_ID}")
                self._initialize_sheet_if_empty()
            else:
                print("[Warning] GOOGLE_SHEET_ID not defined in configuration.")
        except Exception as e:
            print(f"[Error] Failed to connect to Google Sheets: {e}")

    def _initialize_sheet_if_empty(self):
        """Seeds headers and sample data into a blank sheet.
        Controlled by SEED_SAMPLE_DATA in config/env (default: true).
        """
        try:
            records = self.sheet.get_all_values()
            is_empty = not records or len(records) == 0 or not records[0] or records[0][0] == ""
            if is_empty:
                print("[Info] Sheet appears empty. Initializing headers...")
                self.sheet.update("A1", [HEADERS])

                if config.SEED_SAMPLE_DATA:
                    samples = _load_default_samples()
                    if samples:
                        rows_to_insert = [
                            [sample.get(h, "") for h in HEADERS]
                            for sample in samples
                        ]
                        self.sheet.update("A2", rows_to_insert)
                        print(f"[Info] Sheet seeded with {len(samples)} sample records from sample_leads.json.")
                    else:
                        print("[Info] No sample_leads.json found — sheet initialized with headers only.")
                else:
                    print("[Info] SEED_SAMPLE_DATA=false — skipping sample data seeding.")
        except Exception as e:
            print(f"[Warning] Could not initialize sheet: {e}")

    def read_leads(self):
        if not self.sheet:
            print("[Warning] No active sheet connection.")
            return []

        try:
            return self.sheet.get_all_records()
        except Exception as e:
            print(f"[Error] Failed to read leads from Sheet: {e}")
            return []

    def write_back(self, data):
        """Writes enriched leads back to the sheet.
        Uses a safe write: clears and rewrites all rows atomically in one API call.
        Falls back to local JSON if the sheet is unavailable.
        """
        if not self.sheet:
            print("[Info] No Google Sheets connection. Saving locally instead.")
            self._save_local_json(data)
            return

        try:
            if not data:
                print("[Warning] No data to write.")
                return

            rows_to_write = [HEADERS]
            for lead in data:
                row = [
                    lead.get("Company Name", ""),
                    lead.get("Sector", ""),
                    lead.get("Country", ""),
                    lead.get("Official Website", lead.get("website", "")),
                    lead.get("Email", lead.get("email", "")),
                    lead.get("Phone", lead.get("phone", "")),
                    lead.get("LinkedIn Company Page", lead.get("linkedin", "")),
                    lead.get("Source URL", lead.get("source_url", "")),
                    lead.get("Confidence Score", lead.get("quality_score", "")),
                    lead.get("Status/Error", lead.get("status", "")),
                ]
                rows_to_write.append(row)

            # Write all rows in one atomic operation (header + data)
            # This avoids a partial-write window from a separate clear() call
            self.sheet.update("A1", rows_to_write)
            # Clear any leftover rows from a previous longer run
            total_written = len(rows_to_write)
            sheet_row_count = len(self.sheet.get_all_values())
            if sheet_row_count > total_written:
                self.sheet.delete_rows(total_written + 1, sheet_row_count)

            print(f"[Success] Updated {len(data)} rows in Google Sheets.")
        except Exception as e:
            print(f"[Error] Failed to write back to Google Sheet: {e}")
            self._save_local_json(data)

    def _save_local_json(self, data):
        filepath = config.OUTPUT_JSON_PATH
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"[Success] Enriched leads saved locally to: {os.path.abspath(filepath)}")
        except Exception as e:
            print(f"[Error] Could not save fallback JSON: {e}")