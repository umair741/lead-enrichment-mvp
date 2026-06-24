import re

def clean_company_name(name):
    """Strips common suffixes and formatting from company name for cleaner search results."""
    if not name:
        return ""
    # Convert to string and strip spaces
    name = str(name).strip()
    # Remove common corporate indicators case-insensitively
    pattern = r"\b(LLC|Inc\.|Inc|Corp\.|Corp|Corporation|Co\.|Co|Ltd\.|Ltd)\b"
    name = re.sub(pattern, "", name, flags=re.IGNORECASE)
    # Remove extra whitespaces
    return " ".join(name.split())

def clean_email(email):
    """Cleans and validates email syntax."""
    if not email:
        return ""
    email = str(email).strip().lower()
    # Basic email verification regex
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if re.match(pattern, email):
        return email
    return ""

def clean_phone(phone):
    """Standardizes phone numbers (retains digits and leading plus sign)."""
    if not phone:
        return ""
    phone = str(phone).strip()
    # Retain only numbers and '+'
    is_plus = phone.startswith("+")
    digits = "".join(filter(str.isdigit, phone))
    if not digits:
        return ""
    return f"+{digits}" if is_plus else digits

def deduplicate_leads(leads):
    """Removes duplicate companies from the input leads list to optimize scraping requests."""
    seen = set()
    deduplicated = []
    for lead in leads:
        company = lead.get("Company", "")
        website = lead.get("Website", "")
        if not company and not website:
            continue
        
        # Unique key is company name (if exists) or website domain
        key = clean_company_name(company).lower() if company else website.lower()
        if key not in seen:
            seen.add(key)
            deduplicated.append(lead)
    return deduplicated
