"""GitHub Trending collector — scrapes trending.git.ci (JSON API) or falls back to gh-trending API."""
import time
from typing import Any, Dict, List

import requests
from bs4 import BeautifulSoup

from src.utils.logger import setup_logger
from src.utils.retry import retry

logger = setup_logger(__name__)


class GitHubTrendingCollector:
    TRENDING_URL = "https://github.com/trending"
    AI_SEARCH_URL = "https://api.github.com/search/repositories"

    def __init__(self, language: str = "", since: str = "daily") -> None:
        self.language = language
        self.since = since  # daily | weekly | monthly
        self._headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "saurabh-labs-intelligence/1.0",
        }

    @retry(max_attempts=3, delay=2.0)
    def fetch_trending(self, limit: int = 20) -> List[Dict[str, Any]]:
        logger.info("Fetching GitHub trending (%s)", self.since)
        params: Dict[str, str] = {"since": self.since}
        if self.language:
            params["l"] = self.language
        resp = requests.get(
            self.TRENDING_URL, params=params,
            headers={"User-Agent": "Mozilla/5.0 (compatible; saurabh-labs/1.0)"},
            timeout=20,
        )
        resp.raise_for_status()
        return self._parse_html(resp.text)[:limit]

    @retry(max_attempts=3, delay=1.0)
    def fetch_ai_repos(self, limit: int = 10) -> List[Dict[str, Any]]:
        logger.info("Fetching GitHub AI/LLM repos")
        query = "topic:llm topic:ai-agent stars:>100 pushed:>2024-01-01"
        resp = requests.get(
            self.AI_SEARCH_URL,
            params={"q": query, "sort": "stars", "order": "desc", "per_page": limit},
            headers=self._headers,
            timeout=15,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        return [
            {
                "name": r["full_name"],
                "description": r.get("description", ""),
                "stars": r.get("stargazers_count", 0),
                "language": r.get("language", ""),
                "url": r["html_url"],
                "topics": r.get("topics", []),
            }
            for r in items
        ]

    def collect(self) -> Dict[str, Any]:
        try:
            trending = self.fetch_trending()
        except Exception as exc:
            logger.warning("Trending scrape failed: %s", exc)
            trending = []
        ai_repos = self.fetch_ai_repos()
        return {"trending": trending, "ai_repos": ai_repos}

    @staticmethod
    def _parse_html(html: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        repos: List[Dict[str, Any]] = []
        for article in soup.select("article.Box-row"):
            name_tag = article.select_one("h2 a")
            name = name_tag.get_text(strip=True).replace("\n", "").replace(" ", "") if name_tag else ""
            href = name_tag.get("href", "") if name_tag else ""
            url = f"https://github.com{href}" if href else ""
            desc_tag = article.select_one("p")
            description = desc_tag.get_text(strip=True) if desc_tag else ""
            stars_tag = article.select_one("a[href$='/stargazers']")
            stars_text = stars_tag.get_text(strip=True).replace(",", "") if stars_tag else "0"
            try:
                stars = int(stars_text.replace("k", "000").replace(".", ""))
            except ValueError:
                stars = 0
            lang_tag = article.select_one("[itemprop='programmingLanguage']")
            language = lang_tag.get_text(strip=True) if lang_tag else ""
            repos.append({"name": name, "url": url, "description": description, "stars": stars, "language": language})
        return repos
