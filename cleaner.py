import re
import urllib.parse
import phonenumbers

def clean_company_name(name):
    """Strips common suffixes and formatting from company name for cleaner search results."""
    if not name:
        return ""
    name = str(name).strip()
    pattern = r"\b(LLC|Inc\.|Inc|Corp\.|Corp|Corporation|Co\.|Co|Ltd\.|Ltd)\b"
    name = re.sub(pattern, "", name, flags=re.IGNORECASE)
    return " ".join(name.split())

FAKE_EMAIL_DOMAINS = {
    "exemple.extension", "example.com", "example.org", "example.net",
    "test.com", "test.org", "domain.com", "yourdomain.com",
    "yoursite.com", "email.com", "company.com", "sample.com",
}

def clean_email(email):
    """Cleans and validates email syntax. Rejects placeholder/fake emails."""
    if not email:
        return ""
    email = str(email).strip().lower()
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    if not re.match(pattern, email):
        return ""

    domain = email.split("@")[-1]
    if domain in FAKE_EMAIL_DOMAINS:
        return ""
    # Catch generic placeholder patterns like "exemple", "example", "test", "sample" in domain
    if re.search(r"\b(exemple|example|test|sample|placeholder|dummy)\b", domain):
        return ""

    return email

# TLD → ISO 3166-1 alpha-2 country code mapping
# Used to infer country from a website domain when no country is provided
TLD_TO_COUNTRY = {
    "fr": "FR", "de": "DE", "es": "ES", "it": "IT",
    "co.uk": "GB", "uk": "GB", "us": "US", "ca": "CA",
    "be": "BE", "nl": "NL", "ch": "CH", "pt": "PT",
    "pl": "PL", "at": "AT", "se": "SE", "no": "NO",
    "dk": "DK", "fi": "FI", "ie": "IE", "ro": "RO",
    "cz": "CZ", "hu": "HU", "gr": "GR", "tr": "TR",
    "au": "AU", "nz": "NZ", "in": "IN", "jp": "JP",
    "br": "BR", "mx": "MX", "ar": "AR", "za": "ZA",
    "ru": "RU", "cn": "CN", "kr": "KR", "sg": "SG",
}


def country_from_website(website):
    """Infers an ISO country code from a website's domain TLD.

    Examples:
        kusmi.fr          → 'FR'
        company.co.uk     → 'GB'
        example.de        → 'DE'
        example.com       → None  (generic TLD — no country info)
        example.org       → None
    Returns None if TLD is generic (.com, .org, .net, .io, etc.)
    """
    if not website:
        return None
    try:
        hostname = urllib.parse.urlparse(website).hostname or ""
        hostname = hostname.lower().lstrip("www.")
        # Check two-part TLDs first (e.g. co.uk, com.au)
        parts = hostname.rsplit(".", 2)
        if len(parts) >= 3:
            two_part = f"{parts[-2]}.{parts[-1]}"
            if two_part in TLD_TO_COUNTRY:
                return TLD_TO_COUNTRY[two_part]
        # Single TLD (e.g. .fr, .de)
        tld = parts[-1] if parts else ""
        return TLD_TO_COUNTRY.get(tld)  # Returns None for .com, .org, .net, etc.
    except Exception:
        return None


def clean_phone(phone, country_code=None, website=None):
    """Validates and standardizes phone numbers using the phonenumbers library.

    Priority order for determining country context:
    1. Try international parse (no hint) — works for any number with a +XX prefix.
    2. Try TLD from website URL — e.g. kusmi.fr → FR, company.de → DE.
    3. Try the provided country_code hint — from the lead's Country field.
    4. Return "" — never save a number we can't confidently validate.
    """
    if not phone:
        return ""
    phone = str(phone).strip()

    # Try 1: International parse — handles +XX prefix for any country
    try:
        parsed = phonenumbers.parse(phone, None)
        if phonenumbers.is_valid_number(parsed):
            return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    except Exception:
        pass

    # Build a list of country hints to try, best-first
    hints = []
    tld_country = country_from_website(website)
    if tld_country:
        hints.append(tld_country)          # e.g. 'FR' from kusmi.fr
    if country_code and country_code != tld_country:
        hints.append(country_code)         # e.g. 'FR' from lead's Country field

    # Try 2 & 3: Each hint in order
    for hint in hints:
        try:
            parsed = phonenumbers.parse(phone, hint)
            if phonenumbers.is_valid_number(parsed):
                return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        except Exception:
            pass

    return ""

def deduplicate_leads(leads):
    """Removes duplicate companies from the input leads list."""
    seen = set()
    deduplicated = []
    for lead in leads:
        company = lead.get("Company Name", "")
        website = lead.get("Official Website", "")
        if not company and not website:
            continue

        key = clean_company_name(company).lower() if company else website.lower()
        if key not in seen:
            seen.add(key)
            deduplicated.append(lead)
    return deduplicated