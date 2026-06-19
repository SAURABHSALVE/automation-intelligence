"""Space, Physics & Science Report analyzer (10:30 PM IST)."""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from src.analyzers.base_analyzer import BaseAnalyzer, PROJECT_ROOT
from src.collectors.space_collector import SpaceCollector
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

PROMPT_FILE = "prompts/space_prompt.md"


class SpaceAnalyzer(BaseAnalyzer):
    def __init__(self) -> None:
        super().__init__(PROMPT_FILE)

    def collect_all(self) -> Dict[str, Any]:
        return SpaceCollector().collect()

    def analyze(self, data: Dict[str, Any]) -> str:
        logger.info("Analyzing space & science data with OpenAI...")
        today = datetime.now().strftime("%A, %B %d, %Y")

        apod = data.get("nasa_apod", {})
        neos = data.get("near_earth_objects", [])
        astronauts = data.get("iss_astronauts", [])
        spacex = data.get("spacex_latest_launch", {})

        context_lines = [f"Today is {today}."]
        if apod.get("title"):
            context_lines.append(f"NASA APOD today: '{apod['title']}' — {apod.get('explanation', '')[:200]}")
        if neos:
            context_lines.append(f"{len(neos)} near-Earth objects in today's data.")
        if astronauts:
            names = [a.get("name") for a in astronauts]
            context_lines.append(f"Currently in space: {', '.join(names[:6])} ({len(astronauts)} total).")
        if spacex.get("name"):
            context_lines.append(f"Latest SpaceX mission: {spacex['name']} (success={spacex.get('success')}).")

        context = " ".join(context_lines)

        user_msg = f"""{context}

Here is today's complete space, physics, and science intelligence data:

{self._format_data_for_prompt(data)}

Generate the complete Space & Science Intelligence Brief following the structure in your instructions.
- Make every fact feel viscerally real with scale comparisons
- Find the 3 most viral-worthy stories and give them proper treatment
- The video ideas must be based on REAL data from today's collection
- The mind-blowing facts section must include at least 3 facts derived from today's actual data
Be awe-inspiring, scientifically accurate, and deeply shareable."""

        return self._call_openai(user_msg)

    def run(self) -> Dict[str, Any]:
        data = self.collect_all()
        report = self.analyze(data)
        date_str = datetime.now().strftime("%Y-%m-%d")
        report_path = PROJECT_ROOT / "reports" / f"space_{date_str}.md"
        report_path.parent.mkdir(exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        logger.info("Space report saved to %s", report_path)
        return {"report": report, "path": str(report_path), "date": date_str, "type": "space"}
