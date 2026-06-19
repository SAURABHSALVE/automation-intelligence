"""Geopolitics + History + GK Report analyzer (9:30 PM IST)."""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from src.analyzers.base_analyzer import BaseAnalyzer, PROJECT_ROOT
from src.collectors.news_collector import NewsCollector
from src.collectors.reddit_collector import RedditCollector
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

PROMPT_FILE = "prompts/geo_prompt.md"


class GeoAnalyzer(BaseAnalyzer):
    def __init__(self) -> None:
        super().__init__(PROMPT_FILE)

    def collect_all(self) -> Dict[str, Any]:
        logger.info("=== Collecting geopolitics intelligence data ===")
        data: Dict[str, Any] = {}

        try:
            data["world_news"] = NewsCollector(hours_back=24).collect(mode="geo")
        except Exception as exc:
            logger.error("Geo news failed: %s", exc)
            data["world_news"] = {}

        try:
            data["reddit_geo"] = RedditCollector(limit=8).collect(mode="geo")
        except Exception as exc:
            logger.error("Reddit geo failed: %s", exc)
            data["reddit_geo"] = {}

        data["context"] = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "day_of_week": datetime.now().strftime("%A"),
            "day_of_year": datetime.now().timetuple().tm_yday,
        }

        return data

    def analyze(self, data: Dict[str, Any]) -> str:
        logger.info("Analyzing geopolitics data with OpenAI...")
        today = datetime.now().strftime("%A, %B %d, %Y")
        user_msg = f"""Today is {today}. Day {data['context']['day_of_year']} of the year.

Here is today's collected geopolitical and world affairs data:

{self._format_data_for_prompt(data)}

Generate the complete Geopolitics + History + GK Report following the structure in your instructions.
- Analyze global power dynamics
- Note any historical anniversaries for today's date
- Share fascinating facts and science discoveries
- Create compelling documentary/video ideas
Be authoritative, educational, and deeply insightful."""
        return self._call_openai(user_msg)

    def run(self) -> Dict[str, Any]:
        data = self.collect_all()
        report = self.analyze(data)
        date_str = datetime.now().strftime("%Y-%m-%d")
        report_path = PROJECT_ROOT / "reports" / f"geo_{date_str}.md"
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        logger.info("Geo report saved to %s", report_path)
        return {"report": report, "path": str(report_path), "date": date_str, "type": "geo"}
