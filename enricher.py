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
    #  SOURCE 2: DuckDuckGo Instant Answer API
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    #  SOURCE 3: DuckDuckGo HTML Search
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    #  SOURCE 4: Bing Search
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    #  HTML Parsing: Extract emails, phones, LinkedIn
    # ------------------------------------------------------------------ #
    def parse_page_content(self, html):
        data = {"emails": [], "phones": [], "linkedin": ""}
        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text(separator=" ")

        # Emails
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        all_emails = re.findall(email_pattern, page_text)
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip()
                if re.match(email_pattern, email):
                    all_emails.insert(0, email)
        data["emails"] = list(dict.fromkeys(all_emails))

        # Phones
        phone_patterns = [
            r"\+?1?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}",
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

        # LinkedIn
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if "linkedin.com/company/" in href:
                data["linkedin"] = href
                break
            elif "linkedin.com/in/" in href and not data["linkedin"]:
                data["linkedin"] = href

        return data

    # ------------------------------------------------------------------ #
    #  Website Crawling: homepage + hardcoded + discovered subpages
    # ------------------------------------------------------------------ #
    def crawl_website(self, base_url):
        combined = {"emails": [], "phones": [], "linkedin": ""}

        if not base_url.startswith("http"):
            base_url = "https://" + base_url

        pages_to_check = [base_url]

        # 1. Fetch homepage
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

            # Hardcoded common subpages - try regardless of homepage links
            base = base_url.rstrip("/")
            hardcoded_subpages = [
                base + "/contact",
                base + "/contact-us",
                base + "/about",
                base + "/about-us",
                base + "/team",
                base + "/support",
            ]
            for hp in hardcoded_subpages:
                if hp not in pages_to_check:
                    pages_to_check.append(hp)

            # Also discover links from homepage
            soup = BeautifulSoup(response.text, "html.parser")
            subpage_keywords = ["contact", "about", "team", "support", "impressum"]
            found_subpages = set()
            for link in soup.find_all("a", href=True):
                href_lower = link["href"].lower()
                for keyword in subpage_keywords:
                    if keyword in href_lower and href_lower not in found_subpages:
                        full_url = urllib.parse.urljoin(base_url, link["href"])
                        if full_url != base_url and full_url not in pages_to_check:
                            found_subpages.add(full_url)
                            pages_to_check.append(full_url)
                        break

        except Exception as e:
            print(f"  [Crawl] Failed to fetch homepage {base_url}: {e}")
            return combined

        # 2. Crawl subpages (limit to 7)
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

        # Deduplicate
        combined["emails"] = list(dict.fromkeys(combined["emails"]))
        combined["phones"] = list(dict.fromkeys(combined["phones"]))
        return combined

    # ------------------------------------------------------------------ #
    #  Pick best email
    # ------------------------------------------------------------------ #
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

    # ------------------------------------------------------------------ #
    #  Main enrichment orchestrator
    # ------------------------------------------------------------------ #
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
                website = "https://" + clearbit_result["domain"]
                print(f"  [Clearbit] Found: {website}")

        if not website and company_name:
            print(f"  [2/4] Checking DuckDuckGo API...")
            ddg_url = self.search_duckduckgo_instant(company_name)
            if ddg_url:
                website = ddg_url
                print(f"  [DDG API] Found: {website}")

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

        # Crawl website for contacts
        if website:
            print(f"  Crawling website for contacts...")
            crawl_data = self.crawl_website(website)
            enriched["email"] = self.pick_best_email(crawl_data.get("emails", []))
            phones = crawl_data.get("phones", [])
            enriched["phone"] = phones[0] if phones else ""
            if crawl_data.get("linkedin"):
                enriched["linkedin"] = crawl_data["linkedin"]

        # Find LinkedIn separately if not found
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