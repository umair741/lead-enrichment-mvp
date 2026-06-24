import json
import os
import gspread
from google.oauth2.service_account import Credentials
import config

# Define expected column headers for our Lead Automation
HEADERS = ["Company", "Website", "Phone", "Email", "LinkedIn", "Source URL", "Status", "Quality Score"]

# Sample data to populate if sheet is completely blank
DEFAULT_SAMPLES = [
    {"Company": "Zaiqa e Lazzat", "Website": "https://www.zaiqaelazzat.com"},
    {"Company": "Kababjees Restaurant", "Website": "https://kababjees.com"},
    {"Company": "Kolachi Restaurant", "Website": "https://www.kolachi.com"},
    {"Company": " Lal Qila Karachi", "Website": "https://lalqila.com"},
    {"Company": "Student Biryani", "Website": "https://studentbiryani.com"},
    {"Company": "Savour Foods", "Website": "https://savourfoods.com"},
    {"Company": "Tuscany Courtyard", "Website": "https://tuscanycourtyard.com"},
    {"Company": "Salt n Pepper", "Website": "https://saltnpepper.com.pk"},
    {"Company": "Bundu Khan", "Website": "https://bundukhan.pk"},
    {"Company": "Gloria Jeans Pakistan", "Website": "https://gloriajeanscoffees.com.pk"},
    {"Company": "Monal Islamabad", "Website": "https://themonal.com"},
    {"Company": "Optimus Technology", "Website": "https://optimustech.co"},
    {"Company": "Cozy Haleem", "Website": "https://cozyhaleem.com"},
    {"Company": "Bolan Sajji", "Website": "https://bolansajjihouse.com.pk"},
    {"Company": "Ginsoy Karachi", "Website": "https://ginsoy.co"}
]

class SheetsClient:
    def __init__(self):
        self.client = None
        self.sheet = None
        self._authenticate()

    def _authenticate(self):
        """Connects to Google Sheets API using credentials.json."""
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
        """Initializes column headers and sample data if sheet is completely empty."""
        try:
            records = self.sheet.get_all_values()
            is_empty = not records or len(records) == 0 or not records[0] or records[0][0] == ""
            if is_empty:
                print("[Info] Sheet appears empty. Initializing headers and sample leads...")
                # Write headers as row 1
                self.sheet.update("A1", [HEADERS])
                # Write some sample rows
                rows_to_insert = []
                for sample in DEFAULT_SAMPLES:
                    row = [sample.get(h, "") for h in HEADERS]
                    rows_to_insert.append(row)
                self.sheet.update("A2", rows_to_insert)
                print("[Info] Sheet initialized with headers and sample records.")
        except Exception as e:
            print(f"[Warning] Could not initialize sheet: {e}")

    def read_leads(self):
        """Reads all lead records from the worksheet."""
        if not self.sheet:
            print("[Warning] No active sheet connection. Reading fallback local sample data...")
            return []
        
        try:
            return self.sheet.get_all_records()
        except Exception as e:
            print(f"[Error] Failed to read leads from Sheet: {e}")
            return []

    def write_back(self, data):
        """Writes enriched leads data back to the sheet or falls back to local JSON."""
        if not self.sheet:
            print("[Info] No Google Sheets connection. Saving to 'enriched_leads_output.json' locally.")
            self._save_local_json(data)
            return

        try:
            if not data:
                return

            # Construct row matrix including headers
            rows_to_write = [HEADERS]
            for lead in data:
                row = [lead.get(h, "") for h in HEADERS]
                rows_to_write.append(row)

            self.sheet.clear()
            self.sheet.update("A1", rows_to_write)
            print(f"[Success] Updated {len(data)} rows in Google Sheets.")
        except Exception as e:
            print(f"[Error] Failed to write back to Google Sheet: {e}")
            self._save_local_json(data)

    def _save_local_json(self, data):
        """Helper to write local JSON backup."""
        filepath = "enriched_leads_output.json"
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"[Success] Enriched leads saved locally to: {os.path.abspath(filepath)}")
        except Exception as e:
            print(f"[Error] Could not save fallback JSON: {e}")
