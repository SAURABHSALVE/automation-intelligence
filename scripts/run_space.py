#!/usr/bin/env python3
"""Space, Physics & Science Brief — full pipeline runner."""
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.analyzers.space_analyzer import SpaceAnalyzer
from src.emailer.email_sender import EmailSender
from src.notion.notion_client import NotionReportSaver
from src.utils.logger import setup_logger

logger = setup_logger("run_space")


def main() -> None:
    logger.info("==================================")
    logger.info("  SAURABH LABS — SPACE SCIENCE RUN")
    logger.info("==================================")

    result = SpaceAnalyzer().run()
    report, date_str = result["report"], result["date"]
    logger.info("Report generated (%d chars) → %s", len(report), result["path"])

    if os.getenv("NOTION_API_KEY") and os.getenv("NOTION_DATABASE_ID"):
        try:
            url = NotionReportSaver().save_report("space", report, date_str)
            logger.info("Notion page: %s", url)
        except Exception as exc:
            logger.error("Notion save failed: %s", exc)
    else:
        logger.warning("Notion credentials not set — skipping")

    if os.getenv("EMAIL_ADDRESS") and os.getenv("EMAIL_PASSWORD"):
        try:
            EmailSender().send("space", report, date_str)
        except Exception as exc:
            logger.error("Email failed: %s", exc)
    else:
        logger.warning("Email credentials not set — skipping")

    logger.info("Space run complete.")


if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
