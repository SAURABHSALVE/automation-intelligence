#!/usr/bin/env python3
"""Geopolitics + History + GK Brief — full pipeline runner."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.analyzers.geo_analyzer import GeoAnalyzer
from src.emailer.email_sender import EmailSender
from src.notion.notion_client import NotionReportSaver
from src.utils.logger import setup_logger

logger = setup_logger("run_geo")


def main() -> None:
    logger.info("==================================")
    logger.info("  SAURABH LABS — GEO HISTORY RUN")
    logger.info("==================================")

    result = GeoAnalyzer().run()
    report, date_str = result["report"], result["date"]
    logger.info("Report generated (%d chars) → %s", len(report), result["path"])

    if os.getenv("NOTION_API_KEY") and os.getenv("NOTION_DATABASE_ID"):
        try:
            url = NotionReportSaver().save_report("geo", report, date_str)
            logger.info("Notion page: %s", url)
        except Exception as exc:
            logger.error("Notion save failed: %s", exc)
    else:
        logger.warning("Notion credentials not set — skipping")

    if os.getenv("EMAIL_ADDRESS") and os.getenv("EMAIL_PASSWORD"):
        try:
            EmailSender().send("geo", report, date_str)
        except Exception as exc:
            logger.error("Email failed: %s", exc)
    else:
        logger.warning("Email credentials not set — skipping")

    logger.info("Geo run complete.")


if __name__ == "__main__":
    main()
