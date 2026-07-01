# 🚀 Lead Enrichment MVP (France Optimized)

Automatically enriches a list of company names with key contact details (website, email, phone, and LinkedIn) scraped from public web sources, then writes the results back to a Google Sheet.

> 🇫🇷 **France MVP Specialization:** Per client requirements, this pipeline is optimized specifically for French companies, targeting French websites, prioritizing French legal pages (e.g., *Mentions légales*), and extracting French phone formats (`+33` and `01-09` local formats).

---

## 📋 Features

- **Google Sheets Integration:** Reads leads and writes enriched data back automatically.
- **Smart Web Finder:** Searches websites via Clearbit Autocomplete, DuckDuckGo, and Bing, applying fuzzy matching to prevent incorrect domain selection.
- **France-Prioritized Crawling:** Prioritizes crawling legally mandated French contact pages like *Mentions légales* and *Contactez-nous*.
- **JS-Heavy Website Support:** Falls back to Playwright headless browser automation if a standard crawler fails to load page contents.
- **Phone Validation:** Extracts and standardizes French phone numbers using the `phonenumbers` library.
- **Confidence Scoring:** Assigns a 1-5 quality score and status labels (Verified, Enriched, Partial, Needs Review, Rejected).

---

## 🗂️ Project File Structure

- `main.py` — Pipeline coordinator (reads leads, calls enricher/cleaner, saves backup, writes back to Sheet).
- `enricher.py` — Web scraping, searching (Clearbit, DDG, Bing), page crawling, and Playwright integration.
- `cleaner.py` — Data cleaning/normalizing (replaces company suffixes, cleans emails/phones).
- `scorer.py` — Scoring engine based on field availability.
- `sheets_client.py` — Connection client to read/write from/to Google Sheets.
- `config.py` — Loads all configurations from the `.env` file.
- `sample_leads.json` — Sample French leads database to seed blank sheets.
- `requirements.txt` — Python external dependency packages.

---

## ⚙️ Setup & Installation Instructions

Follow these step-by-step instructions to configure and run the MVP.

### 🔑 1. Required Credentials & Config Files

You need **two main keys/files** placed in your project root folder:
1. **`credentials.json`:** Your Google Cloud Service Account key file.
2. **`.env`:** A configuration file defining your Google Sheet ID.

---

### Step 2 — Create and Activate a Virtual Environment

Open your terminal in the project root folder and execute:

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows PowerShell)
.\venv\Scripts\activate

# Activate virtual environment (macOS / Linux)
source venv/bin/activate
```

---

### Step 3 — Install Dependencies

Install the Python libraries listed in `requirements.txt`:

```bash
pip install -r requirements.txt
```

---

### Step 4 — Install Playwright Browser Binaries

Playwright requires Chromium binaries for headless browsing. Install them by running:

```bash
playwright install chromium
```
*(If you run into permissions errors on Windows, run the terminal as Administrator or execute `python -m playwright install chromium`)*

---

### Step 5 — Setup Google Sheets API

To connect the pipeline to your Google Sheet:

#### 5a. Create a Google Cloud Project & Enable APIs
1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a **New Project** and name it (e.g. `lead-enrichment-pipeline`).
3. Navigate to **APIs & Services > Library**.
4. Search for and enable **both** of the following APIs:
   - ✅ **Google Sheets API**
   - ✅ **Google Drive API**

#### 5b. Generate a Service Account Key
1. Go to **APIs & Services > Credentials**.
2. Click **Create Credentials** and choose **Service Account**.
3. Fill in the account name (e.g. `sheet-updater`) and click **Create and Continue**, then click **Done**.
4. Click on your newly created service account email from the list.
5. Select the **Keys** tab, click **Add Key > Create new key**, choose **JSON**, and click **Create**.
6. A JSON key file will download. **Rename this file to `credentials.json`** and save it in the root folder of this project.

#### 5c. Share the Google Sheet with the Service Account
1. Open your target Google Sheet.
2. Click **Share** in the top right.
3. Open `credentials.json` and copy the `"client_email"` value (looks like `sheet-updater@yourproject.iam.gserviceaccount.com`).
4. Paste it into the Share window, set their role to **Editor**, and click **Send**.

---

### Step 6 — Configure the Environment Variables (`.env`)

Create a file named `.env` in the project root folder and paste the following content:

```env
# ── Google Sheets Setup ──────────────────────────────────────
# The ID of your Google Sheet (extracted from its URL)
GOOGLE_SHEET_ID=your_sheet_id_here
GOOGLE_SHEETS_CREDENTIALS_PATH=credentials.json
GOOGLE_SHEET_NAME=Sheet1

# ── Seeding & Backups ───────────────────────────────────────
# Set to "false" to prevent writing sample leads if sheet is blank
SEED_SAMPLE_DATA=true
OUTPUT_JSON_PATH=enriched_leads_output.json

# ── Localization & Headers ──────────────────────────────────
# Enforced country context for local phone number formatting
DEFAULT_PHONE_COUNTRY=FR
USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36
```

> **Where to find the Google Sheet ID?**
> In your browser's address bar when editing your sheet:
> `https://docs.google.com/spreadsheets/d/[GOOGLE_SHEET_ID_IS_HERE]/edit`

---

## ▶️ How to Run the Pipeline

Ensure your virtual environment is active, then run:

```bash
python main.py
```

### Initial Run & Seeding:
If the sheet is completely blank, the pipeline will initialize it by writing the standard column headers. If `SEED_SAMPLE_DATA` is `true`, it will auto-populate the sheet with 25 French test companies from `sample_leads.json`. Run the script a second time to begin crawling and enriching those companies.

---

## 🔒 Security Notes

- **Never commit credentials:** Both `.env` and `credentials.json` are listed in `.gitignore` to prevent committing secrets to version control.
- **No external API costs:** No paid Search APIs (e.g. ZenRows, Google Search API) are required. The script crawls using free, open-access search scrapers.
