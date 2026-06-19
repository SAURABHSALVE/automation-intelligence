"""Product Hunt collector using their public GraphQL API."""
from datetime import date
from typing import Any, Dict, List

import requests

from src.utils.logger import setup_logger
from src.utils.retry import retry

logger = setup_logger(__name__)

PH_GRAPHQL = "https://api.producthunt.com/v2/api/graphql"

TOP_POSTS_QUERY = """
query TopPosts($date: Date!) {
  posts(order: VOTES, postedAfter: $date, first: 20) {
    edges {
      node {
        id
        name
        tagline
        description
        votesCount
        commentsCount
        url
        website
        topics {
          edges {
            node { name }
          }
        }
      }
    }
  }
}
"""


class ProductHuntCollector:
    def __init__(self, api_token: str = "") -> None:
        self.api_token = api_token

    @retry(max_attempts=2, delay=2.0, exceptions=(requests.ConnectionError, requests.Timeout))
    def fetch_top_posts(self, limit: int = 15) -> List[Dict[str, Any]]:
        logger.info("Fetching Product Hunt top posts")
        today = date.today().isoformat()
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        resp = requests.post(
            PH_GRAPHQL,
            json={"query": TOP_POSTS_QUERY, "variables": {"date": today}},
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
        edges = data.get("data", {}).get("posts", {}).get("edges", [])
        posts = []
        for e in edges[:limit]:
            node = e["node"]
            topics = [t["node"]["name"] for t in node.get("topics", {}).get("edges", [])]
            posts.append({
                "name": node.get("name", ""),
                "tagline": node.get("tagline", ""),
                "description": (node.get("description") or "")[:400],
                "votes": node.get("votesCount", 0),
                "comments": node.get("commentsCount", 0),
                "url": node.get("url", ""),
                "topics": topics,
            })
        return sorted(posts, key=lambda x: x["votes"], reverse=True)

    def collect(self) -> Dict[str, Any]:
        if not self.api_token:
            logger.info("Product Hunt: no API token set — skipping")
            return {"top_posts": []}
        try:
            posts = self.fetch_top_posts()
        except Exception as exc:
            logger.warning("Product Hunt collection failed: %s", exc)
            posts = []
        return {"top_posts": posts}
