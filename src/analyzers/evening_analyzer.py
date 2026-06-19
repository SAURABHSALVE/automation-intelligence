"""Evening Tech Report analyzer (9 PM IST)."""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from src.analyzers.base_analyzer import BaseAnalyzer, PROJECT_ROOT
from src.collectors.github_trending import GitHubTrendingCollector
from src.collectors.hackernews import HackerNewsCollector
from src.collectors.news_collector import NewsCollector
from src.collectors.product_hunt import ProductHuntCollector
from src.collectors.reddit_collector import RedditCollector
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

PROMPT_FILE = "prompts/evening_prompt.md"


class EveningAnalyzer(BaseAnalyzer):
    def __init__(self, ph_token: str = "") -> None:
        super().__init__(PROMPT_FILE)
        self.ph_token = ph_token

    def collect_all(self) -> Dict[str, Any]:
        logger.info("=== Collecting evening intelligence data ===")
        data: Dict[str, Any] = {}

        try:
            data["hackernews"] = HackerNewsCollector(hours_back=12).collect()
        except Exception as exc:
            logger.error("HN failed: %s", exc)
            data["hackernews"] = {}

        try:
            data["tech_news"] = NewsCollector(hours_back=12).collect(mode="tech")
        except Exception as exc:
            logger.error("Tech news failed: %s", exc)
            data["tech_news"] = {}

        try:
            data["ai_news"] = NewsCollector(hours_back=12).collect(mode="ai")
        except Exception as exc:
            logger.error("AI news failed: %s", exc)
            data["ai_news"] = {}

        try:
            data["reddit_tech"] = RedditCollector(limit=6).collect(mode="tech")
        except Exception as exc:
            logger.error("Reddit tech failed: %s", exc)
            data["reddit_tech"] = {}

        try:
            data["github"] = GitHubTrendingCollector().collect()
        except Exception as exc:
            logger.error("GitHub failed: %s", exc)
            data["github"] = {}

        try:
            data["product_hunt"] = ProductHuntCollector(api_token=self.ph_token).collect()
        except Exception as exc:
            logger.error("Product Hunt failed: %s", exc)
            data["product_hunt"] = {}

        return data

    def analyze(self, data: Dict[str, Any]) -> str:
        logger.info("Analyzing evening data with OpenAI...")
        today = datetime.now().strftime("%A, %B %d, %Y")
        user_msg = f"""Today is {today}.

Here is the collected tech intelligence data from the past 12 hours:

{self._format_data_for_prompt(data)}

Generate the complete Evening Tech Brief following the structure in your instructions. Focus on the most exciting launches, AI startup news, consumer tech, hardware, social media trends, and viral content opportunities. Be energetic and forward-looking."""
        return self._call_openai(user_msg)

    def run(self) -> Dict[str, Any]:
        data = self.collect_all()
        report = self.analyze(data)
        date_str = datetime.now().strftime("%Y-%m-%d")
        report_path = PROJECT_ROOT / "reports" / f"evening_{date_str}.md"
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        logger.info("Evening report saved to %s", report_path)
        return {"report": report, "path": str(report_path), "date": date_str, "type": "evening"}
