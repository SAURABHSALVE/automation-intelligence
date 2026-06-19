"""Reddit collector using RSS feeds (no auth, no 403 blocks)."""
import time
import xml.etree.ElementTree as ET
from typing import Any, Dict, List

import requests

from src.utils.logger import setup_logger
from src.utils.retry import retry

logger = setup_logger(__name__)

AI_SUBREDDITS = [
    "MachineLearning", "artificial", "ChatGPT",
    "LocalLLaMA", "OpenAI", "singularity", "datascience",
]
TECH_SUBREDDITS = [
    "technology", "programming", "webdev", "startups", "ProductManagement",
]
GEO_SUBREDDITS = [
    "worldnews", "geopolitics", "india", "Economics", "CredibleDefense",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


class RedditCollector:
    BASE = "https://www.reddit.com"

    def __init__(self, limit: int = 10) -> None:
        self.limit = limit

    @retry(max_attempts=2, delay=5.0, exceptions=(requests.ConnectionError, requests.Timeout))
    def _fetch_subreddit_rss(self, sub: str, sort: str = "hot") -> List[Dict[str, Any]]:
        url = f"{self.BASE}/r/{sub}/{sort}.rss"
        resp = requests.get(url, headers=HEADERS, params={"limit": self.limit}, timeout=20)
        if resp.status_code == 429:
            logger.warning("Reddit r/%s rate-limited (429) — skipping", sub)
            return []
        resp.raise_for_status()
        return self._parse_rss(sub, resp.text)

    def _collect(self, subreddits: List[str]) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for sub in subreddits:
            try:
                posts = self._fetch_subreddit_rss(sub)
                if posts:
                    results.extend(posts)
                    time.sleep(3)   # only sleep when we actually got data
            except Exception as exc:
                logger.warning("Reddit r/%s failed: %s", sub, exc)
        return results

    def collect_ai(self) -> List[Dict[str, Any]]:
        return self._collect(AI_SUBREDDITS)

    def collect_tech(self) -> List[Dict[str, Any]]:
        return self._collect(TECH_SUBREDDITS)

    def collect_geo(self) -> List[Dict[str, Any]]:
        return self._collect(GEO_SUBREDDITS)

    def collect(self, mode: str = "all") -> Dict[str, Any]:
        if mode == "ai":
            return {"ai": self.collect_ai()}
        if mode == "tech":
            return {"tech": self.collect_tech()}
        if mode == "geo":
            return {"geo": self.collect_geo()}
        return {"ai": self.collect_ai(), "tech": self.collect_tech(), "geo": self.collect_geo()}

    @staticmethod
    def _parse_rss(sub: str, xml_text: str) -> List[Dict[str, Any]]:
        NS = {
            "atom": "http://www.w3.org/2005/Atom",
            "media": "http://search.yahoo.com/mrss/",
        }
        posts = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
            logger.warning("RSS parse error for r/%s: %s", sub, exc)
            return posts

        for entry in root.findall(".//atom:entry", NS):
            title_el = entry.find("atom:title", NS)
            link_el  = entry.find("atom:link",  NS)
            content_el = entry.find("atom:content", NS)
            author_el  = entry.find(".//atom:name", NS)
            updated_el = entry.find("atom:updated", NS)

            title   = (title_el.text or "").strip() if title_el is not None else ""
            link    = link_el.get("href", "") if link_el is not None else ""
            content = (content_el.text or "")[:500].strip() if content_el is not None else ""
            author  = (author_el.text or "").strip() if author_el is not None else ""
            updated = updated_el.text if updated_el is not None else ""

            posts.append({
                "subreddit": sub,
                "title": title,
                "url": link,
                "selftext": content,
                "author": author,
                "published": updated,
                "score": 0,     # RSS doesn't expose score; sorted by recency
                "comments": 0,
            })
        return posts
