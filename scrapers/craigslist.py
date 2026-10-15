import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
import re
from typing import List, Optional
from datetime import datetime
import hashlib

from models import JobLead
from scrapers.base import BaseScraper

class CraigslistScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="Craigslist Residential Gigs")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

    def _normalize_city(self, location: str) -> str:
        """Map common city names to craigslist subdomains."""
        cleaned = location.lower().strip()
        city_map = {
            "new york": "newyork",
            "los angeles": "losangeles",
            "san francisco": "sfbay",
            "chicago": "chicago",
            "houston": "houston",
            "dallas": "dallas",
            "austin": "austin",
            "miami": "miami",
            "atlanta": "atlanta",
            "seattle": "seattle",
            "denver": "denver",
            "phoenix": "phoenix",
            "philadelphia": "philadelphia",
            "boston": "boston",
            "san diego": "sandiego",
            "las vegas": "lasvegas",
            "orlando": "orlando",
            "tampa": "tampa"
        }
        for k, v in city_map.items():
            if k in cleaned:
                return v
        # Default fallback: replace spaces with empty
        return re.sub(r'[^a-z0-9]', '', cleaned) or "newyork"

    def search_jobs(self, trade: str, location: str, limit: int = 15) -> List[JobLead]:
        city_subdomain = self._normalize_city(location)
        
        # Searching skilled trade gigs (sbg) and labor gigs (lbg)
        # We query the RSS feed first as it provides clean structured data without bot challenges
        categories = ["sbg", "lbg"]
        leads = []
        seen_urls = set()

        for cat in categories:
            if len(leads) >= limit:
                break
            
            url = f"https://{city_subdomain}.craigslist.org/search/{cat}?query={trade}&format=rss"
            try:
                resp = requests.get(url, headers=self.headers, timeout=10)
                if resp.status_code == 200 and resp.content:
                    parsed_leads = self._parse_rss(resp.content, location, trade)
                    for lead in parsed_leads:
                        if lead.url not in seen_urls:
                            seen_urls.add(lead.url)
                            leads.append(lead)
                            if len(leads) >= limit:
                                break
            except Exception as e:
                # If network fails or subdomain doesn't exist, log and continue
                print(f"[Craigslist] Notice: Query for {cat} returned error: {e}")

        # If RSS returns few or no items, try HTML search as secondary fallback
        if len(leads) < limit:
            try:
                html_url = f"https://{city_subdomain}.craigslist.org/search/sbg?query={trade}"
                resp = requests.get(html_url, headers=self.headers, timeout=10)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    # modern craigslist uses .cl-static-search-result or .result-node
                    items = soup.select(".cl-static-search-result, .result-node, li.cl-search-result")
                    for item in items:
                        if len(leads) >= limit:
                            break
                        link_tag = item.find("a")
                        if not link_tag:
                            continue
                        post_url = link_tag.get("href", "")
                        if post_url in seen_urls:
                            continue
                        
                        title = link_tag.get_text(strip=True) or (item.find(".title") and item.find(".title").get_text(strip=True))
                        if not title:
                            continue

                        # Extract location text if present
                        loc_tag = item.find(class_=re.compile(r"location|meta"))
                        loc_text = loc_tag.get_text(strip=True) if loc_tag else location

                        seen_urls.add(post_url)
                        uid = hashlib.md5(post_url.encode()).hexdigest()[:10]
                        leads.append(JobLead(
                            id=f"cl-{uid}",
                            title=title,
                            source="Craigslist",
                            url=post_url,
                            location=loc_text,
                            description=title,
                            detected_trade=trade
                        ))
            except Exception as e:
                print(f"[Craigslist] HTML fallback error: {e}")

        return leads

    def _parse_rss(self, xml_content: bytes, default_location: str, trade: str) -> List[JobLead]:
        leads = []
        try:
            root = ET.fromstring(xml_content)
            # RDF format: channel and items with namespace http://purl.org/rss/1.0/
            # or standard RSS 2.0
            items = root.findall(".//{http://purl.org/rss/1.0/}item") or root.findall(".//item")
            
            for item in items:
                title_elem = item.find("{http://purl.org/rss/1.0/}title") or item.find("title")
                link_elem = item.find("{http://purl.org/rss/1.0/}link") or item.find("link")
                desc_elem = item.find("{http://purl.org/rss/1.0/}description") or item.find("description")
                date_elem = item.find("{http://purl.org/dc/elements/1.1/}date") or item.find("pubDate")

                title = title_elem.text.strip() if (title_elem is not None and title_elem.text) else "Untitled Job"
                link = link_elem.text.strip() if (link_elem is not None and link_elem.text) else ""
                desc = desc_elem.text.strip() if (desc_elem is not None and desc_elem.text) else title
                
                # Strip HTML from description if any
                if "<" in desc:
                    desc = BeautifulSoup(desc, "html.parser").get_text()

                # Extract budget if mentioned (e.g. $200, $50/hr)
                budget_match = re.search(r'\$\d+(?:,\d+)?(?:\s*-\s*\$?\d+)?(?:\s*(?:/hr|hr|per hour))?', f"{title} {desc}", re.IGNORECASE)
                extracted_budget = budget_match.group(0) if budget_match else None

                # Generate clean ID
                uid = hashlib.md5(link.encode() if link else title.encode()).hexdigest()[:10]

                leads.append(JobLead(
                    id=f"cl-{uid}",
                    title=title,
                    source="Craigslist",
                    url=link,
                    location=default_location,
                    description=desc,
                    detected_trade=trade,
                    extracted_budget=extracted_budget
                ))
        except Exception as e:
            print(f"[Craigslist] RSS parsing exception: {e}")
        return leads
