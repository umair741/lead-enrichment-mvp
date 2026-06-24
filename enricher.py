import re
import time
import urllib.parse
import requests
from bs4 import BeautifulSoup
import config


class LeadEnricher:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": config.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })

    # ------------------------------------------------------------------ #
    #  SOURCE 1: Clearbit Autocomplete API (free, no key needed)
    # ------------------------------------------------------------------ #
    def search_clearbit(self, company_name):
        """
        Uses Clearbit's free autocomplete API to find domain/website.
        Returns dict with 'domain' and 'logo' or empty dict.
        """
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

    # ------------------------------------------------------------------ #
    #  SOURCE 2: DuckDuckGo Instant Answer API (structured JSON, open)
    # ------------------------------------------------------------------ #
    def search_duckduckgo_instant(self, company_name):
        """
        Uses DuckDuckGo's Instant Answer API to find website URL.
        Returns the official URL if available.
        """
        try:
            url = "https://api.duckduckgo.com/"
            params = {"q": company_name, "format": "json", "no_html": 1, "skip_disambig": 1}
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                # Check AbstractURL (usually the Wikipedia/official link)
                abstract_url = data.get("AbstractURL", "")
                official_url = data.get("Results", [])
                
                # Check for direct official website in Results
                if official_url:
                    for result in official_url:
                        first_url = result.get("FirstURL", "")
                        if first_url and "wikipedia" not in first_url:
                            return first_url

                # Infobox can have profile URLs (LinkedIn, website, etc.)
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

    # ------------------------------------------------------------------ #
    #  SOURCE 3: DuckDuckGo HTML Search (fallback web search)
    # ------------------------------------------------------------------ #
    def search_duckduckgo_html(self, query):
        """Scrapes DuckDuckGo HTML lite search results page."""
        urls = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                # Try multiple selectors for result links
                for link in soup.find_all("a", class_="result__a"):
                    href = link.get("href", "")
                    if href:
                        parsed = urllib.parse.urlparse(href)
                        qs = urllib.parse.parse_qs(parsed.query)
                        if "uddg" in qs:
                            urls.append(qs["uddg"][0])
                        elif href.startswith("http"):
                            urls.append(href)
                            
                # Fallback: try result__url class
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

    # ------------------------------------------------------------------ #
    #  SOURCE 4: Bing Search (fallback search engine)
    # ------------------------------------------------------------------ #
    def search_bing(self, query):
        """Scrapes Bing search results as a fallback source."""
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

    # ------------------------------------------------------------------ #
    #  HTML Parsing: Extract emails, phones, LinkedIn from page content
    # ------------------------------------------------------------------ #
    def parse_page_content(self, html):
        """Extracts email, phone, and LinkedIn links from HTML content."""
        data = {"emails": [], "phones": [], "linkedin": ""}
        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text(separator=" ")

        # --- Emails: find ALL matches, then pick the best one later ---
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        all_emails = re.findall(email_pattern, page_text)
        # Also check mailto: links which are very reliable
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip()
                if re.match(email_pattern, email):
                    all_emails.insert(0, email)  # prioritize mailto links
        data["emails"] = list(dict.fromkeys(all_emails))  # deduplicate, preserve order

        # --- Phones: find ALL matches ---
        phone_patterns = [
            r"\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}",       # US/CA format
            r"\+?\d{1,4}[\s.-]?\(?\d{1,5}\)?[\s.-]?\d{3,4}[\s.-]?\d{3,4}",  # International
        ]
        for pattern in phone_patterns:
            matches = re.findall(pattern, page_text)
            data["phones"].extend(matches)
        # Also check tel: links
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("tel:"):
                phone = href.replace("tel:", "").strip()
                data["phones"].insert(0, phone)
        data["phones"] = list(dict.fromkeys(data["phones"]))  # deduplicate

        # --- LinkedIn ---
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "linkedin.com/company/" in href:
                data["linkedin"] = href
                break
            elif "linkedin.com/in/" in href and not data["linkedin"]:
                data["linkedin"] = href

        return data

    # ------------------------------------------------------------------ #
    #  Website Crawling: homepage + contact/about pages
    # ------------------------------------------------------------------ #
    def crawl_website(self, base_url):
        """Crawls a website's homepage plus contact/about subpages."""
        combined = {"emails": [], "phones": [], "linkedin": ""}

        # Ensure URL has scheme
        if not base_url.startswith("http"):
            base_url = "https://" + base_url

        pages_to_check = [base_url]

        # 1. Fetch homepage and discover subpages
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

            # Find contact/about links to scrape next
            soup = BeautifulSoup(response.text, "html.parser")
            subpage_keywords = ["contact", "about", "team", "support", "impressum"]
            found_subpages = set()
            for link in soup.find_all("a", href=True):
                href_lower = link["href"].lower()
                for keyword in subpage_keywords:
                    if keyword in href_lower and href_lower not in found_subpages:
                        full_url = urllib.parse.urljoin(base_url, link["href"])
                        if full_url != base_url:
                            found_subpages.add(full_url)
                            pages_to_check.append(full_url)
                        break
        except Exception as e:
            print(f"  [Crawl] Failed to fetch homepage {base_url}: {e}")
            return combined

        # 2. Crawl discovered subpages (limit to 3 extra pages)
        for subpage_url in pages_to_check[1:4]:
            try:
                time.sleep(0.5)  # be polite
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

        # Deduplicate
        combined["emails"] = list(dict.fromkeys(combined["emails"]))
        combined["phones"] = list(dict.fromkeys(combined["phones"]))
        return combined

    # ------------------------------------------------------------------ #
    #  Pick best email (prefer direct/personal over generic)
    # ------------------------------------------------------------------ #
    def pick_best_email(self, emails):
        """Selects the best email, preferring personal over generic addresses."""
        if not emails:
            return ""
        generic_prefixes = ["info@", "support@", "noreply@", "no-reply@",
                            "admin@", "webmaster@", "help@", "sales@", "marketing@"]
        # First pass: find a non-generic email
        for email in emails:
            email_lower = email.lower()
            if not any(email_lower.startswith(prefix) for prefix in generic_prefixes):
                return email
        # Fallback: return the first email even if generic
        return emails[0]

    # ------------------------------------------------------------------ #
    #  Main enrichment orchestrator
    # ------------------------------------------------------------------ #
    def enrich_company(self, company_name, existing_website=None):
        """
        Enriches a company using multiple sources in priority order:
        1. Clearbit free API -> get domain
        2. DuckDuckGo Instant Answer API -> get website
        3. DuckDuckGo HTML search -> fallback website search
        4. Bing search -> last resort website search
        5. Crawl discovered website for contacts
        6. Search for LinkedIn separately if not found
        """
        print(f"  Enriching: {company_name}")
        enriched = {
            "website": "",
            "phone": "",
            "email": "",
            "linkedin": "",
            "source_url": ""
        }

        # ---- Step 1: Find the company's website/domain ----
        website = existing_website or ""

        if website:
            print(f"  [Direct] Using provided website: {website}")
        
        # Try Clearbit first (most reliable for domains)
        if not website and company_name:
            print(f"  [1/4] Checking Clearbit...")
            clearbit_result = self.search_clearbit(company_name)
            if clearbit_result.get("domain"):
                website = "https://" + clearbit_result["domain"]
                print(f"  [Clearbit] Found: {website}")

        # Try DuckDuckGo Instant Answer API
        if not website and company_name:
            print(f"  [2/4] Checking DuckDuckGo API...")
            ddg_url = self.search_duckduckgo_instant(company_name)
            if ddg_url:
                website = ddg_url
                print(f"  [DDG API] Found: {website}")

        # Try DuckDuckGo HTML search
        if not website and company_name:
            print(f"  [3/4] Searching DuckDuckGo HTML...")
            ddg_urls = self.search_duckduckgo_html(f"{company_name} official website")
            ignored = ["duckduckgo.com", "linkedin.com", "facebook.com",
                        "twitter.com", "yelp.com", "yellowpages.com", "wikipedia.org"]
            for url in ddg_urls:
                if not any(domain in url for domain in ignored):
                    website = url
                    print(f"  [DDG HTML] Found: {website}")
                    break

        # Try Bing as last resort
        if not website and company_name:
            print(f"  [4/4] Searching Bing...")
            bing_urls = self.search_bing(f"{company_name} official website")
            ignored = ["linkedin.com", "facebook.com", "twitter.com",
                        "yelp.com", "yellowpages.com", "wikipedia.org"]
            for url in bing_urls:
                if not any(domain in url for domain in ignored):
                    website = url
                    print(f"  [Bing] Found: {website}")
                    break

        enriched["website"] = website
        enriched["source_url"] = website

        # ---- Step 2: Crawl the website for contact details ----
        if website:
            print(f"  Crawling website for contacts...")
            crawl_data = self.crawl_website(website)

            enriched["email"] = self.pick_best_email(crawl_data.get("emails", []))
            phones = crawl_data.get("phones", [])
            enriched["phone"] = phones[0] if phones else ""
            if crawl_data.get("linkedin"):
                enriched["linkedin"] = crawl_data["linkedin"]

        # ---- Step 3: Find LinkedIn separately if not found on website ----
        if not enriched["linkedin"]:
            print(f"  Searching for LinkedIn page...")
            # Build a likely LinkedIn URL
            slug = company_name.lower().replace(" ", "-").replace(".", "")
            enriched["linkedin"] = f"https://www.linkedin.com/company/{slug}"

            # Try to verify via DuckDuckGo
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
