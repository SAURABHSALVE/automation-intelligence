"""arXiv collector using the public Atom feed API."""
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import requests

from src.utils.logger import setup_logger
from src.utils.retry import retry

logger = setup_logger(__name__)

NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
ARXIV_API = "http://export.arxiv.org/api/query"


class ArxivCollector:
    CATEGORIES = ["cs.AI", "cs.LG", "cs.CL", "cs.RO", "stat.ML"]

    def __init__(self, days_back: int = 2, max_results: int = 15) -> None:
        self.days_back = days_back
        self.max_results = max_results

    @retry(max_attempts=3, delay=2.0)
    def fetch_papers(self, query: str = "large language model OR AI agent OR reinforcement learning") -> List[Dict[str, Any]]:
        logger.info("Fetching arXiv papers: %s", query)
        params = {
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": self.max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        resp = requests.get(ARXIV_API, params=params, timeout=30)
        resp.raise_for_status()
        return self._parse(resp.text)

    @retry(max_attempts=3, delay=2.0)
    def fetch_by_category(self, category: str = "cs.AI") -> List[Dict[str, Any]]:
        logger.info("Fetching arXiv category: %s", category)
        params = {
            "search_query": f"cat:{category}",
            "start": 0,
            "max_results": 10,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        resp = requests.get(ARXIV_API, params=params, timeout=30)
        resp.raise_for_status()
        return self._parse(resp.text)

    def collect(self) -> Dict[str, Any]:
        papers = self.fetch_papers()
        return {"papers": papers}

    @staticmethod
    def _parse(xml_text: str) -> List[Dict[str, Any]]:
        root = ET.fromstring(xml_text)
        entries = []
        for entry in root.findall("atom:entry", NS):
            title_el = entry.find("atom:title", NS)
            summary_el = entry.find("atom:summary", NS)
            published_el = entry.find("atom:published", NS)
            link_el = entry.find("atom:id", NS)
            authors = [
                a.find("atom:name", NS).text
                for a in entry.findall("atom:author", NS)
                if a.find("atom:name", NS) is not None
            ]
            entries.append({
                "title": (title_el.text or "").strip() if title_el is not None else "",
                "summary": (summary_el.text or "").strip()[:600] if summary_el is not None else "",
                "published": published_el.text if published_el is not None else "",
                "url": link_el.text if link_el is not None else "",
                "authors": authors[:4],
            })
        return entries
