#!/usr/bin/env python3
"""Morning Intelligence Report — full pipeline runner."""
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path and is the working directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from src.analyzers.morning_analyzer import MorningAnalyzer
from src.emailer.email_sender import EmailSender
from src.notion.notion_client import NotionReportSaver
from src.utils.logger import setup_logger

logger = setup_logger("run_morning")


def main() -> None:
    logger.info("==============================")
    logger.info("  SAURABH LABS — MORNING RUN")
    logger.info("==============================")

    ph_token = os.getenv("PRODUCT_HUNT_API_TOKEN", "")
    result = MorningAnalyzer(ph_token=ph_token).run()
    report, date_str = result["report"], result["date"]
    logger.info("Report generated (%d chars) → %s", len(report), result["path"])

    if os.getenv("NOTION_API_KEY") and os.getenv("NOTION_DATABASE_ID"):
        try:
            url = NotionReportSaver().save_report("morning", report, date_str)
            logger.info("Notion page: %s", url)
        except Exception as exc:
            logger.error("Notion save failed: %s", exc)
    else:
        logger.warning("Notion credentials not set — skipping")

    if os.getenv("EMAIL_ADDRESS") and os.getenv("EMAIL_PASSWORD"):
        try:
            EmailSender().send("morning", report, date_str)
        except Exception as exc:
            logger.error("Email failed: %s", exc)
    else:
        logger.warning("Email credentials not set — skipping")

    logger.info("Morning run complete.")


if __name__ == "__main__":
    import traceback
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
