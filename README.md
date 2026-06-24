# Lead Automation MVP

An automated lead enrichment pipeline that reads company names from a Google Sheet, scrapes their websites for contact details, scores the lead quality, and writes enriched data back to the sheet.

---

## What It Does

```
Google Sheet (Input)          Enrichment Engine              Google Sheet (Output)
┌──────────────┐    ──►    ┌─────────────────────┐    ──►   ┌──────────────────────┐
│ Company Name │           │ 1. Find Website     │          │ Company              │
│ (e.g. Apple) │           │    (Clearbit/DDG/    │          │ Website              │
│              │           │     Bing search)     │          │ Phone                │
│              │           │ 2. Crawl Homepage    │          │ Email                │
│              │           │    + /contact page   │          │ LinkedIn             │
│              │           │ 3. Extract Email,    │          │ Source URL            │
│              │           │    Phone, LinkedIn   │          │ Status               │
│              │           │ 4. Clean & Score     │          │ Quality Score (0-100)│
└──────────────┘           └─────────────────────┘          └──────────────────────┘
```

### Pipeline Steps

1. **Read** company names from your Google Sheet
2. **Deduplicate** to avoid processing the same company twice
3. **Search** for the company website using 4 sources:
   - **Clearbit Autocomplete API** (free, no API key needed) — most reliable
   - **DuckDuckGo Instant Answer API** — structured JSON fallback
   - **DuckDuckGo HTML Search** — web search fallback
   - **Bing Search** — last resort
4. **Crawl** the discovered website:
   - Scrapes the homepage for emails, phones, and LinkedIn links
   - Automatically finds and crawls `/contact`, `/about`, `/team` subpages
   - Checks `mailto:` and `tel:` HTML links (most reliable source)
5. **Clean** the extracted data:
   - Validates email format
   - Standardizes phone number formatting
   - Prefers personal emails over generic ones (e.g. `info@`, `support@`)
6. **Score** each lead (0 to 100):
   - Email found: **+35 points**
   - Phone found: **+25 points**
   - LinkedIn found: **+25 points**
   - Website found: **+15 points**
7. **Write back** enriched data to the Google Sheet + local JSON backup

---

## Project Structure

```
scrapping task/
├── .env                    # Environment variables (Sheet ID, credentials path)
├── credentials.json        # Google Service Account key (you provide this)
├── requirements.txt        # Python dependencies
├── config.py               # Loads environment configuration
├── sheets_client.py        # Google Sheets API read/write operations
├── enricher.py             # Multi-source search + website scraping engine
├── cleaner.py              # Data cleaning (emails, phones, company names)
├── scorer.py               # Lead quality scoring (0-100)
├── main.py                 # Pipeline orchestrator
├── enriched_leads_output.json  # Local backup of enriched results
└── venv/                   # Python virtual environment
```

---

## Setup Instructions

### Prerequisites
- Python 3.8 or higher
- A Google Cloud project with **Google Sheets API** and **Google Drive API** enabled
- A Google Service Account with a downloaded JSON credentials file

### Step 1: Clone / Navigate to the project
```bash
cd "c:\Users\User\Desktop\New folder\scrapping task"
```

### Step 2: Create a virtual environment
```bash
python -m venv venv
venv\Scripts\activate
```

### Step 3: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Configure credentials
1. Place your `credentials.json` file in the project root folder.
2. Create a Google Sheet and copy its ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/<THIS_IS_THE_SHEET_ID>/edit
   ```
3. Share the Google Sheet with the service account email from `credentials.json` (give **Editor** access).
4. Update the `.env` file with your Sheet ID:
   ```env
   GOOGLE_SHEET_ID=your_sheet_id_here
   GOOGLE_SHEETS_CREDENTIALS_PATH=credentials.json
   GOOGLE_SHEET_NAME=Sheet1
   ```

### Step 5: Run the pipeline
```bash
python main.py
```

---

## How It Works — Module by Module

### `config.py`
Loads environment variables from `.env` using `python-dotenv`. Stores Google Sheet credentials path, Sheet ID, sheet name, and the browser User-Agent string used for scraping.

### `sheets_client.py`
Handles all Google Sheets interactions:
- **Authentication**: Connects via `gspread` using a service account
- **Auto-initialization**: If the sheet is empty, it automatically creates column headers and populates sample company rows
- **Read**: Fetches all rows as dictionaries
- **Write**: Clears the sheet and writes enriched data back with headers
- **Fallback**: If Sheets is unavailable, saves results to `enriched_leads_output.json`

### `enricher.py`
The core scraping engine with 4 data sources in priority order:
1. **Clearbit Autocomplete API** — Free, no key needed, returns company domain instantly
2. **DuckDuckGo Instant Answer API** — Returns structured data including official URLs
3. **DuckDuckGo HTML Search** — Scrapes the lite HTML search page
4. **Bing Search** — Last resort web search

Once a website is found, it crawls:
- The homepage
- Up to 3 subpages (`/contact`, `/about`, `/team`, `/support`)
- Extracts emails (regex + `mailto:` links), phones (regex + `tel:` links), and LinkedIn URLs

### `cleaner.py`
Data cleaning utilities:
- `clean_company_name()` — Strips suffixes like "LLC", "Inc.", "Corp."
- `clean_email()` — Validates email format using regex
- `clean_phone()` — Keeps only digits and leading `+`
- `deduplicate_leads()` — Removes duplicate company entries

### `scorer.py`
Grades lead quality from 0 to 100:
| Field    | Points |
|----------|--------|
| Email    | +35    |
| Phone    | +25    |
| LinkedIn | +25    |
| Website  | +15    |

Status labels:
- **High Quality**: Score ≥ 75
- **Medium Quality**: Score ≥ 40
- **Low Quality**: Score > 0
- **Needs Review**: Score = 0

### `main.py`
Orchestrates the full pipeline:
1. Connects to Google Sheets
2. Reads lead rows
3. Deduplicates
4. Enriches each company (with progress logging)
5. Saves local JSON backup
6. Writes back to Google Sheets
7. Prints a results summary table

---

## Example Output

```
=============================================
      Lead Enrichment Pipeline Start
=============================================

Successfully connected to Google Sheet: 1W1m...
Loaded 4 raw company rows.
After deduplication: 4 unique companies.

--- [1/4] Google ---
  Enriching: Google
  [1/4] Checking Clearbit...
  [Clearbit] Found: https://google.com
  Crawling website for contacts...
  Done: website=True, email=False, phone=True, linkedin=True

--- [2/4] Microsoft ---
  ...

=============================================
               RESULTS SUMMARY
=============================================
  Google                    | Score:  65 | Medium Quality
  Microsoft                 | Score:  65 | Medium Quality
  Apple                     | Score:  65 | Medium Quality
  GitHub                    | Score:  40 | Medium Quality
=============================================
```

---

## Current Limitations (MVP)

- Does not handle JavaScript-rendered pages (uses static HTML parsing)
- Search engines may rate-limit after many requests
- Email extraction depends on emails being visible in page HTML
- No CRM integration yet (PerfexCRM planned for future phase)

---

## Future Enhancements

- [ ] PerfexCRM API integration (auto-sync high-quality leads)
- [ ] Proxy rotation for large-scale scraping
- [ ] JavaScript rendering support (Playwright/Selenium)
- [ ] Email verification API integration (Hunter.io / ZeroBounce)
- [ ] Scheduling via cron / task scheduler
- [ ] Dashboard / web UI for monitoring
