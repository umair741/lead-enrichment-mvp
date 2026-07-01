# Lead Enrichment MVP

Automated lead enrichment system that reads company records from Google Sheets, discovers publicly available business information, enriches each lead, calculates a confidence score, and writes the results back to Google Sheets.

The goal of this project is to reduce manual company research for sales teams, recruiters, agencies, and market researchers.

---

## Features

- Google Sheets Integration
- Automated Company Enrichment
- Company Website Discovery
- Business Email Extraction
- Phone Number Extraction & Validation
- LinkedIn Company Page Discovery
- Confidence Scoring
- Lead Quality Classification
- JSON Export
- Duplicate Detection
- Multi-Country Support

---

## How It Works

```text
Google Sheet
      │
      ▼
Read Leads
      │
      ▼
Data Cleaning
      │
      ▼
Duplicate Removal
      │
      ▼
Company Enrichment
      │
      ├── Clearbit Lookup
      ├── DuckDuckGo Search
      └── Website Analysis
      │
      ▼
Email & Phone Validation
      │
      ▼
Confidence Scoring
      │
      ▼
Update Google Sheet
      │
      ▼
JSON Export
```

---

## Project Structure

```text
lead-enrichment-mvp/
│
├── main.py
├── config.py
├── cleaner.py
├── enricher.py
├── scorer.py
├── sheets_client.py
├── sample_leads.json
├── requirements.txt
└── README.md
```

---

## File Overview

### main.py

Main application entry point.

Responsible for:

- Loading configuration
- Reading leads
- Running enrichment
- Calculating scores
- Updating Google Sheets
- Saving JSON output

### sheets_client.py

Handles Google Sheets operations.

Responsible for:

- Reading lead data
- Updating enriched records
- Managing sheet communication

### cleaner.py

Responsible for:

- Cleaning company names
- Standardizing country names
- Removing duplicates
- Validating input data

### enricher.py

Responsible for:

- Company website discovery
- Email extraction
- Phone extraction
- LinkedIn discovery
- Company information enrichment

### scorer.py

Responsible for:

- Lead quality evaluation
- Confidence score calculation
- Status assignment

### config.py

Loads environment variables and project settings.

---

## Installation

### 1. Clone Repository

```bash
git clone <your-repository-url>
cd lead-enrichment-mvp
```

### 2. Create Virtual Environment

```bash
python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright Browser

```bash
playwright install chromium
```

---

## Google Cloud Setup

### Step 1: Create Google Cloud Project

Go to:

https://console.cloud.google.com/

Create a new project.

---

### Step 2: Enable APIs

Enable:

- Google Sheets API
- Google Drive API

---

### Step 3: Create Service Account

1. Open IAM & Admin
2. Service Accounts
3. Create Service Account
4. Generate JSON Key

Download the JSON file.

Rename it to:

```text
credentials.json
```

Place it in the project root directory.

---

### Step 4: Share Your Google Sheet

Open your Google Sheet.

Click:

```text
Share
```

Add the Service Account email.

Example:

```text
lead-enrichment@project-id.iam.gserviceaccount.com
```

Give:

```text
Editor Access
```

---

## Environment Variables

Create a `.env` file in the project root.

```env
GOOGLE_SHEETS_CREDENTIALS_PATH=credentials.json

GOOGLE_SHEET_ID=YOUR_GOOGLE_SHEET_ID

GOOGLE_SHEET_NAME=Sheet1

SEED_SAMPLE_DATA=true

OUTPUT_JSON_PATH=enriched_leads_output.json

DEFAULT_PHONE_COUNTRY=FR
```

---

## Input Format

Google Sheet should contain:

| Company Name | Sector | Country |
|--------------|----------|----------|
| Airbus | Aerospace | France |
| Renault | Automotive | France |

Minimum required field:

```text
Company Name
```

---

## Output Format

The system enriches and writes:

| Company Name | Sector | Country | Official Website | Email | Phone | LinkedIn Company Page | Source URL | Confidence Score | Status/Error |
|--------------|----------|----------|----------|----------|----------|----------|----------|----------|----------|

---

## Running The Project

```bash
python main.py
```

The application will:

1. Read leads from Google Sheets
2. Clean and validate records
3. Enrich company information
4. Calculate confidence scores
5. Update Google Sheets
6. Save JSON output

---

## Confidence Scoring

| Score | Meaning |
|---------|----------|
| 5 | Excellent Match |
| 4 | High Confidence |
| 3 | Partial Information |
| 2 | Needs Review |
| 1 | Low Confidence |

Scoring considers:

- Website Found
- Email Found
- Phone Found
- LinkedIn Found

---

## Status Values

| Status | Description |
|----------|----------|
| Verified | Website, Email and Phone Found |
| Enriched | High Quality Result |
| Partial | Some Information Found |
| Needs Review | Limited Information |
| Rejected | No Useful Information Found |

---

## Example Workflow

### Input

| Company Name | Country |
|----------|----------|
| Airbus | France |

### Output

| Website | Email | Phone | LinkedIn | Score |
|----------|----------|----------|----------|----------|
| airbus.com | contact@airbus.com | +33xxxxxxx | linkedin.com/company/airbus | 5 |

---

## Use Cases

- B2B Lead Generation
- Sales Prospecting
- CRM Enrichment
- Recruitment Research
- Agency Outreach
- Market Research

---

## Limitations

- Some websites block automated scraping.
- Contact information may not always be publicly available.
- Results depend on publicly accessible company data.
- Accuracy varies by region and industry.

---

## Security Notes

- Never commit credentials.json to GitHub.
- Never commit API keys to GitHub.
- Store secrets in environment variables.
- Add credentials files to `.gitignore`.

---

## Future Improvements

- CRM Integrations
- Dashboard UI
- Scheduled Enrichment
- Batch Processing
- Additional Data Sources
- Advanced Lead Scoring

---

## License

This project is provided as an MVP demonstration and educational reference.