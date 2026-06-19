"""Morning Intelligence Report analyzer (7 AM IST)."""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from src.analyzers.base_analyzer import BaseAnalyzer, PROJECT_ROOT
from src.collectors.arxiv_collector import ArxivCollector
from src.collectors.github_trending import GitHubTrendingCollector
from src.collectors.hackernews import HackerNewsCollector
from src.collectors.news_collector import NewsCollector
from src.collectors.product_hunt import ProductHuntCollector
from src.collectors.reddit_collector import RedditCollector
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

PROMPT_FILE = "prompts/morning_prompt.md"


class MorningAnalyzer(BaseAnalyzer):
    def __init__(self, ph_token: str = "") -> None:
        super().__init__(PROMPT_FILE)
        self.ph_token = ph_token

    def collect_all(self) -> Dict[str, Any]:
        logger.info("=== Collecting morning intelligence data ===")
        data: Dict[str, Any] = {}

        logger.info("Collecting Hacker News...")
        try:
            data["hackernews"] = HackerNewsCollector(hours_back=36).collect()
        except Exception as exc:
            logger.error("HN collection failed: %s", exc)
            data["hackernews"] = {}

        logger.info("Collecting GitHub Trending...")
        try:
            data["github"] = GitHubTrendingCollector().collect()
        except Exception as exc:
            logger.error("GitHub collection failed: %s", exc)
            data["github"] = {}

        logger.info("Collecting Reddit...")
        try:
            data["reddit"] = RedditCollector(limit=8).collect(mode="ai")
        except Exception as exc:
            logger.error("Reddit collection failed: %s", exc)
            data["reddit"] = {}

        logger.info("Collecting arXiv papers...")
        try:
            data["arxiv"] = ArxivCollector(days_back=2, max_results=12).collect()
        except Exception as exc:
            logger.error("arXiv collection failed: %s", exc)
            data["arxiv"] = {}

        logger.info("Collecting Product Hunt...")
        try:
            data["product_hunt"] = ProductHuntCollector(api_token=self.ph_token).collect()
        except Exception as exc:
            logger.error("Product Hunt collection failed: %s", exc)
            data["product_hunt"] = {}

        logger.info("Collecting AI news RSS...")
        try:
            data["news"] = NewsCollector(hours_back=36).collect(mode="ai")
        except Exception as exc:
            logger.error("News collection failed: %s", exc)
            data["news"] = {}

        return data

    def analyze(self, data: Dict[str, Any]) -> str:
        logger.info("Analyzing morning data with OpenAI...")
        today = datetime.now().strftime("%A, %B %d, %Y")
        user_msg = f"""Today is {today}.

Here is the collected intelligence data from the last 36 hours:

{self._format_data_for_prompt(data)}

Generate the complete Morning Intelligence Report following the structure defined in your instructions. Be specific, insightful, and actionable. Focus on what developers, founders, and AI enthusiasts care about most."""
        return self._call_openai(user_msg)

    def run(self) -> Dict[str, Any]:
        data = self.collect_all()
        report = self.analyze(data)
        date_str = datetime.now().strftime("%Y-%m-%d")
        report_path = PROJECT_ROOT / "reports" / f"morning_{date_str}.md"
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        logger.info("Morning report saved to %s", report_path)
        return {"report": report, "path": str(report_path), "date": date_str, "type": "morning"}
