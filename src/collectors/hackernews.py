"""Hacker News collector via Algolia Search API (free, no key needed)."""
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests

from src.utils.logger import setup_logger
from src.utils.retry import retry

logger = setup_logger(__name__)

ALGOLIA_SEARCH = "https://hn.algolia.com/api/v1/search"
ALGOLIA_DATE = "https://hn.algolia.com/api/v1/search_by_date"


class HackerNewsCollector:
    def __init__(self, hours_back: int = 36) -> None:
        self.hours_back = hours_back
        self.since_ts = int((datetime.now(timezone.utc) - timedelta(hours=hours_back)).timestamp())

    @retry(max_attempts=3, delay=1.0)
    def _search(self, url: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("hits", [])

    def fetch_top_stories(self, limit: int = 25) -> List[Dict[str, Any]]:
        logger.info("Fetching HN top stories (last %dh)", self.hours_back)
        hits = self._search(
            ALGOLIA_SEARCH,
            {
                "tags": "story",
                "numericFilters": f"created_at_i>{self.since_ts}",
                "hitsPerPage": limit,
            },
        )
        return [self._shape(h) for h in hits]

    def fetch_ai_stories(self, limit: int = 20) -> List[Dict[str, Any]]:
        logger.info("Fetching HN AI/LLM stories")
        queries = ["AI LLM agent", "OpenAI Anthropic Claude", "machine learning deep learning"]
        seen: Dict[str, bool] = {}
        results: List[Dict[str, Any]] = []
        for q in queries:
            hits = self._search(
                ALGOLIA_DATE,
                {
                    "query": q,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{self.since_ts}",
                    "hitsPerPage": limit,
                },
            )
            for h in hits:
                if h.get("objectID") not in seen:
                    seen[h["objectID"]] = True
                    results.append(self._shape(h))
            time.sleep(0.3)
        return results[:limit]

    def collect(self) -> Dict[str, Any]:
        return {
            "top_stories": self.fetch_top_stories(),
            "ai_stories": self.fetch_ai_stories(),
        }

    @staticmethod
    def _shape(hit: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": hit.get("title", ""),
            "url": hit.get("url", f"https://news.ycombinator.com/item?id={hit.get('objectID')}"),
            "points": hit.get("points", 0),
            "comments": hit.get("num_comments", 0),
            "author": hit.get("author", ""),
            "created_at": hit.get("created_at", ""),
        }
