import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Google Sheets Configuration
CREDENTIALS_PATH = os.getenv("GOOGLE_SHEETS_CREDENTIALS_PATH", "credentials.json")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Sheet1")

# Seed sample data into empty sheets? Set to "false" to disable
SEED_SAMPLE_DATA = os.getenv("SEED_SAMPLE_DATA", "true").lower() == "true"

# Output file path for local JSON backup
OUTPUT_JSON_PATH = os.getenv("OUTPUT_JSON_PATH", "enriched_leads_output.json")

# Scraping settings
USER_AGENT = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Default phone country code (ISO 3166-1 alpha-2), used when lead has no Country field
DEFAULT_PHONE_COUNTRY = os.getenv("DEFAULT_PHONE_COUNTRY", "FR")
