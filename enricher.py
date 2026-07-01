import re
import time
import difflib
import urllib.parse
import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import config


def company_name_matches_domain(company_name, domain):
    """
    Verifies that a found domain is actually plausible for the given company name.
    Prevents wrong matches like 'Effy' -> 'effyjewelry.com'.
    Returns True if the domain's core name reasonably matches the company name.
    """
    if not company_name or not domain:
        return False

    # Normalize: lowercase, strip common suffixes, remove spaces/punctuation
    def normalize(s):
        s = s.lower()
        s = re.sub(r"\b(llc|inc|corp|corporation|co|ltd|group|sa|sas|sarl)\b", "", s)
        s = re.sub(r"[^a-z0-9]", "", s)
        return s

    clean_name = normalize(company_name)
    # Extract just the domain name without TLD/subdomain
    domain_core = domain.lower().replace("www.", "").split(".")[0]
    domain_core = re.sub(r"[^a-z0-9]", "", domain_core)

    if not clean_name or not domain_core:
        return False

    # Exact substring match either way = good match
    if clean_name in domain_core or domain_core in clean_name:
        return True

    # Fuzzy similarity check for slight variations
    similarity = difflib.SequenceMatcher(None, clean_name, domain_core).ratio()
    return similarity >= 0.6


class LeadEnricher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    def search_clearbit(self, company_name):
        try:
            url = "https://autocomplete.clearbit.com/v1/companies/suggest"
            params = {"query": company_name}
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                results = response.json()
                if results and len(results) > 0:
                    top = results[0]
                    return {
                        "domain": top.get("domain", ""),
                        "name": top.get("name", ""),
                        "logo": top.get("logo", ""),
                    }
        except Exception as e:
            print(f"  [Clearbit] Failed for '{company_name}': {e}")
        return {}

    def search_duckduckgo_instant(self, company_name):
        try:
            url = "https://api.duckduckgo.com/"
            params = {"q": company_name, "format": "json", "no_html": 1, "skip_disambig": 1}
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                abstract_url = data.get("AbstractURL", "")
                official_url = data.get("Results", [])

                if official_url:
                    for result in official_url:
                        first_url = result.get("FirstURL", "")
                        if first_url and "wikipedia" not in first_url:
                            return first_url

                infobox = data.get("Infobox", {})
                if infobox:
                    for item in infobox.get("content", []):
                        label = item.get("label", "").lower()
                        value = item.get("value", "")
                        if "website" in label or "official" in label:
                            return value

                if abstract_url and "wikipedia" not in abstract_url:
                    return abstract_url
        except Exception as e:
            print(f"  [DDG Instant] Failed for '{company_name}': {e}")
        return ""

    def search_duckduckgo_html(self, query):
        urls = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for link in soup.find_all("a", class_="result__a"):
                    href = link.get("href", "")
                    if href:
                        parsed = urllib.parse.urlparse(href)
                        qs = urllib.parse.parse_qs(parsed.query)
                        if "uddg" in qs:
                            urls.append(qs["uddg"][0])
                        elif href.startswith("http"):
                            urls.append(href)

                if not urls:
                    for link in soup.find_all("a", class_="result__url"):
                        href = link.get("href", "")
                        if href:
                            parsed = urllib.parse.urlparse(href)
                            qs = urllib.parse.parse_qs(parsed.query)
                            if "uddg" in qs:
                                urls.append(qs["uddg"][0])
                            elif href.startswith("http"):
                                urls.append(href)
        except Exception as e:
            print(f"  [DDG HTML] Search failed for '{query}': {e}")
        return urls

    def search_bing(self, query):
        urls = []
        try:
            url = f"https://www.bing.com/search?q={urllib.parse.quote(query)}"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    if href.startswith("http") and "bing.com" not in href and "microsoft.com" not in href:
                        urls.append(href)
        except Exception as e:
            print(f"  [Bing] Search failed for '{query}': {e}")
        return urls

    def parse_page_content(self, html):
        data = {"emails": [], "phones": [], "linkedin": ""}
        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text(separator=" ")

        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        all_emails = re.findall(email_pattern, page_text)
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip()
                if re.match(email_pattern, email):
                    all_emails.insert(0, email)
        data["emails"] = list(dict.fromkeys(all_emails))

        # French + English phone patterns
        phone_patterns = [
            r"\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}",
            r"(?:\+33|0)[1-9](?:[\s.-]*\d{2}){4}",  # French format
            r"\+?\d{1,4}[\s.-]?\(?\d{1,5}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}",
        ]
        for pattern in phone_patterns:
            matches = re.findall(pattern, page_text)
            data["phones"].extend(matches)
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("tel:"):
                phone = href.replace("tel:", "").strip()
                data["phones"].insert(0, phone)
        data["phones"] = list(dict.fromkeys(data["phones"]))

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "linkedin.com/company/" in href:
                data["linkedin"] = href
                break
            elif "linkedin.com/in/" in href and not data["linkedin"]:
                data["linkedin"] = href

        return data

    def crawl_website(self, base_url):
        """
        Crawls homepage + dynamically discovered contact/about pages.
        Uses real links found on the page (works for French, English, any language)
        instead of guessing hardcoded English paths.
        """
        combined = {"emails": [], "phones": [], "linkedin": ""}

        if not base_url.startswith("http"):
            base_url = "https://" + base_url

        pages_to_check = [base_url]

        try:
            response = self.session.get(base_url, timeout=10, allow_redirects=True)
            if response.status_code != 200:
                print(f"  [Crawl] Homepage returned status {response.status_code}")
                return combined

            homepage_data = self.parse_page_content(response.text)
            combined["emails"].extend(homepage_data["emails"])
            combined["phones"].extend(homepage_data["phones"])
            if homepage_data["linkedin"]:
                combined["linkedin"] = homepage_data["linkedin"]

            # Dynamic link discovery - works regardless of language
            # Matches both URL slugs and visible link text
            keywords = [
                "contact", "contactez", "contacter", "nous-contacter",
                "about", "a-propos", "apropos", "qui-sommes",
                "team", "equipe", "groupe",
                "support", "mentions", "legal", "mentions-legales",
            ]

            soup = BeautifulSoup(response.text, "html.parser")
            base_domain = urllib.parse.urlparse(base_url).netloc
            found_subpages = set()

            for link in soup.find_all("a", href=True):
                href = link["href"]
                link_text = link.get_text().strip().lower()
                full_url = urllib.parse.urljoin(base_url, href)

                # Stay on same domain
                if urllib.parse.urlparse(full_url).netloc != base_domain:
                    continue
                if full_url == base_url or full_url in found_subpages:
                    continue

                url_lower = full_url.lower()
                if any(kw in url_lower or kw in link_text for kw in keywords):
                    found_subpages.add(full_url)
                    pages_to_check.append(full_url)

        except Exception as e:
            print(f"  [Crawl] Failed to fetch homepage {base_url}: {e}")
            return combined

        # Crawl up to 6 discovered subpages
        for subpage_url in pages_to_check[1:7]:
            try:
                time.sleep(0.5)
                print(f"  [Crawl] Checking subpage: {subpage_url}")
                resp = self.session.get(subpage_url, timeout=10, allow_redirects=True)
                if resp.status_code == 200:
                    sub_data = self.parse_page_content(resp.text)
                    combined["emails"].extend(sub_data["emails"])
                    combined["phones"].extend(sub_data["phones"])
                    if not combined["linkedin"] and sub_data["linkedin"]:
                        combined["linkedin"] = sub_data["linkedin"]
            except Exception as e:
                print(f"  [Crawl] Failed subpage {subpage_url}: {e}")

        combined["emails"] = list(dict.fromkeys(combined["emails"]))
        combined["phones"] = list(dict.fromkeys(combined["phones"]))

        # ---- Playwright fallback: only if fast crawl found nothing ----
        if not combined["emails"] and not combined["phones"]:
            print(f"  [Fallback] No data via requests, trying Playwright on {base_url}...")
            html = self.crawl_with_playwright(base_url)
            if html:
                pw_data = self.parse_page_content(html)
                combined["emails"].extend(pw_data["emails"])
                combined["phones"].extend(pw_data["phones"])
                if not combined["linkedin"] and pw_data["linkedin"]:
                    combined["linkedin"] = pw_data["linkedin"]
                combined["emails"] = list(dict.fromkeys(combined["emails"]))
                combined["phones"] = list(dict.fromkeys(combined["phones"]))

        return combined

    def crawl_with_playwright(self, url):
        """
        Fallback: renders JavaScript using a headless browser and returns full HTML.
        Used only when the fast requests-based crawl finds no email/phone.
        """
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page(user_agent=config.USER_AGENT)
                page.goto(url, timeout=15000, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)
                html = page.content()
                browser.close()
                return html
        except Exception as e:
            print(f"  [Playwright] Failed for {url}: {e}")
            return ""

    def pick_best_email(self, emails):
        if not emails:
            return ""
        generic_prefixes = ["info@", "support@", "noreply@", "no-reply@",
                            "admin@", "webmaster@", "help@", "sales@", "marketing@"]
        for email in emails:
            email_lower = email.lower()
            if not any(email_lower.startswith(prefix) for prefix in generic_prefixes):
                return email
        return emails[0]

    def enrich_company(self, company_name, existing_website=None):
        print(f"  Enriching: {company_name}")
        enriched = {
            "website": "",
            "phone": "",
            "email": "",
            "linkedin": "",
            "source_url": ""
        }

        website = existing_website or ""

        if website:
            print(f"  [Direct] Using provided website: {website}")

        if not website and company_name:
            print(f"  [1/4] Checking Clearbit...")
            clearbit_result = self.search_clearbit(company_name)
            if clearbit_result.get("domain"):
                candidate = "https://" + clearbit_result["domain"]
                if company_name_matches_domain(company_name, clearbit_result["domain"]):
                    website = candidate
                    print(f"  [Clearbit] Found: {website}")
                else:
                    print(f"  [Clearbit] Rejected mismatch: {candidate} doesn't match '{company_name}'")

        if not website and company_name:
            print(f"  [2/4] Checking DuckDuckGo API...")
            ddg_url = self.search_duckduckgo_instant(company_name)
            if ddg_url:
                domain = urllib.parse.urlparse(ddg_url).netloc
                if company_name_matches_domain(company_name, domain):
                    website = ddg_url
                    print(f"  [DDG API] Found: {website}")
                else:
                    print(f"  [DDG API] Rejected mismatch: {ddg_url} doesn't match '{company_name}'")

        if not website and company_name:
            print(f"  [3/4] Searching DuckDuckGo HTML...")
            ddg_urls = self.search_duckduckgo_html(f"{company_name} official website")
            ignored = ["duckduckgo.com", "linkedin.com", "facebook.com",
                       "twitter.com", "yelp.com", "yellowpages.com", "wikipedia.org"]
            for url in ddg_urls:
                if any(domain in url for domain in ignored):
                    continue
                domain = urllib.parse.urlparse(url).netloc
                if company_name_matches_domain(company_name, domain):
                    website = url
                    print(f"  [DDG HTML] Found: {website}")
                    break
                else:
                    print(f"  [DDG HTML] Skipping mismatch: {url}")

        if not website and company_name:
            print(f"  [4/4] Searching Bing...")
            bing_urls = self.search_bing(f"{company_name} official website")
            ignored = ["linkedin.com", "facebook.com", "twitter.com",
                       "yelp.com", "yellowpages.com", "wikipedia.org"]
            for url in bing_urls:
                if any(domain in url for domain in ignored):
                    continue
                domain = urllib.parse.urlparse(url).netloc
                if company_name_matches_domain(company_name, domain):
                    website = url
                    print(f"  [Bing] Found: {website}")
                    break
                else:
                    print(f"  [Bing] Skipping mismatch: {url}")

        enriched["website"] = website
        enriched["source_url"] = website

        if website:
            print(f"  Crawling website for contacts...")
            crawl_data = self.crawl_website(website)
            enriched["email"] = self.pick_best_email(crawl_data.get("emails", []))
            phones = crawl_data.get("phones", [])
            enriched["phone"] = phones[0] if phones else ""
            if crawl_data.get("linkedin"):
                enriched["linkedin"] = crawl_data["linkedin"]

        if not enriched["linkedin"]:
            print(f"  Searching for LinkedIn page...")
            slug = company_name.lower().replace(" ", "-").replace(".", "")
            enriched["linkedin"] = f"https://www.linkedin.com/company/{slug}"

            li_urls = self.search_duckduckgo_html(f"{company_name} site:linkedin.com/company")
            for url in li_urls:
                if "linkedin.com/company/" in url:
                    enriched["linkedin"] = url
                    break

        print(f"  Done: website={bool(enriched['website'])}, "
              f"email={bool(enriched['email'])}, "
              f"phone={bool(enriched['phone'])}, "
              f"linkedin={bool(enriched['linkedin'])}")
        return enriched