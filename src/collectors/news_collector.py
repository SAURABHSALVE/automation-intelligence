"""RSS-based news collector — works without any API key."""
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse

import requests

from src.utils.logger import setup_logger
from src.utils.retry import retry

logger = setup_logger(__name__)

AI_FEEDS = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/"),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/"),
    ("MIT Tech Review", "https://www.technologyreview.com/feed/"),
    ("Wired", "https://www.wired.com/feed/rss"),
]

TECH_FEEDS = [
    ("TechCrunch", "https://techcrunch.com/feed/"),
    ("The Verge", "https://www.theverge.com/rss/index.xml"),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index"),
    ("Hacker News RSS", "https://hnrss.org/frontpage?points=100"),
]

GEO_FEEDS = [
    ("BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml"),
    ("The Guardian World", "https://www.theguardian.com/world/rss"),
    ("NPR World", "https://feeds.npr.org/1004/rss.xml"),
    ("The Hindu India", "https://www.thehindu.com/news/national/feeder/default.rss"),
]

HEADERS = {"User-Agent": "saurabh-labs-intelligence/1.0 (RSS reader)"}


class NewsCollector:
    def __init__(self, hours_back: int = 36) -> None:
        self.cutoff = datetime.now(timezone.utc) - timedelta(hours=hours_back)

    @retry(max_attempts=3, delay=2.0)
    def _fetch_feed(self, name: str, url: str) -> List[Dict[str, Any]]:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        return self._parse_rss(name, resp.text)

    def _collect_feeds(self, feeds: List[tuple]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for name, url in feeds:
            try:
                items = self._fetch_feed(name, url)
                results.extend(items)
                time.sleep(0.3)
            except Exception as exc:
                logger.warning("Feed '%s' failed: %s", name, exc)
        return results

    def collect_ai_news(self) -> List[Dict[str, Any]]:
        logger.info("Collecting AI news from RSS feeds")
        return self._collect_feeds(AI_FEEDS)

    def collect_tech_news(self) -> List[Dict[str, Any]]:
        logger.info("Collecting tech news from RSS feeds")
        return self._collect_feeds(TECH_FEEDS)

    def collect_geo_news(self) -> List[Dict[str, Any]]:
        logger.info("Collecting geo/world news from RSS feeds")
        return self._collect_feeds(GEO_FEEDS)

    def collect(self, mode: str = "all") -> Dict[str, Any]:
        if mode == "ai":
            return {"ai_news": self.collect_ai_news()}
        if mode == "tech":
            return {"tech_news": self.collect_tech_news()}
        if mode == "geo":
            return {"geo_news": self.collect_geo_news()}
        return {
            "ai_news": self.collect_ai_news(),
            "tech_news": self.collect_tech_news(),
            "geo_news": self.collect_geo_news(),
        }

    @staticmethod
    def _parse_rss(source: str, xml_text: str) -> List[Dict[str, Any]]:
        items = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return items
        ns_map = {"atom": "http://www.w3.org/2005/Atom"}
        # Handle both RSS 2.0 and Atom
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            description = (item.findtext("description") or "")[:400].strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            items.append({"source": source, "title": title, "url": link, "summary": description, "published": pub_date})
        for entry in root.findall(".//atom:entry", ns_map):
            title_el = entry.find("atom:title", ns_map)
            link_el = entry.find("atom:link", ns_map)
            summary_el = entry.find("atom:summary", ns_map)
            pub_el = entry.find("atom:published", ns_map)
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = link_el.get("href", "") if link_el is not None else ""
            summary = (summary_el.text or "")[:400].strip() if summary_el is not None else ""
            pub = pub_el.text if pub_el is not None else ""
            items.append({"source": source, "title": title, "url": link, "summary": summary, "published": pub})
        return items
