"""Gmail SMTP email sender with beautiful HTML emails."""
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Optional

import markdown

from src.utils.logger import setup_logger
from src.utils.retry import retry

logger = setup_logger(__name__)

# Absolute project root: src/emailer -> src -> root
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

SUBJECTS = {
    "morning": "🌅 Saurabh Labs Morning Intelligence — {date}",
    "evening": "🌆 Saurabh Labs Evening Tech Brief — {date}",
    "geo": "🌍 Saurabh Labs Geo & History Brief — {date}",
}

TEMPLATE_MAP = {
    "morning": "src/templates/morning_email.html",
    "evening": "src/templates/evening_email.html",
    "geo": "src/templates/geo_email.html",
}


class EmailSender:
    def __init__(self) -> None:
        self.email = os.environ["EMAIL_ADDRESS"]
        self.password = os.environ["EMAIL_PASSWORD"]
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.recipient = os.getenv("EMAIL_RECIPIENT") or self.email

    def _load_template(self, report_type: str) -> str:
        rel = TEMPLATE_MAP.get(report_type, TEMPLATE_MAP["morning"])
        return (PROJECT_ROOT / rel).read_text(encoding="utf-8")

    def _markdown_to_html(self, md_text: str) -> str:
        # "extra" already includes tables; avoid duplicate extension warning
        return markdown.markdown(
            md_text,
            extensions=["extra", "toc", "fenced_code"],
        )

    def _build_email(self, report_type: str, report_md: str, date_str: str) -> MIMEMultipart:
        msg = MIMEMultipart("alternative")
        subject = SUBJECTS.get(report_type, "Saurabh Labs Intelligence").format(date=date_str)
        msg["Subject"] = subject
        msg["From"] = f"Saurabh Labs Intelligence <{self.email}>"
        msg["To"] = self.recipient

        report_html = self._markdown_to_html(report_md)
        template = self._load_template(report_type)
        full_html = (
            template
            .replace("{{REPORT_CONTENT}}", report_html)
            .replace("{{DATE}}", date_str)
            .replace("{{REPORT_TYPE}}", report_type.upper())
        )

        msg.attach(MIMEText(report_md, "plain", "utf-8"))
        msg.attach(MIMEText(full_html, "html", "utf-8"))
        return msg

    @retry(max_attempts=3, delay=5.0, exceptions=(smtplib.SMTPException, OSError))
    def send(self, report_type: str, report_md: str, date_str: Optional[str] = None) -> None:
        if date_str is None:
            date_str = datetime.now().strftime("%B %d, %Y")

        logger.info("Sending %s email to %s", report_type, self.recipient)
        msg = self._build_email(report_type, report_md, date_str)

        with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(self.email, self.password)
            server.sendmail(self.email, self.recipient, msg.as_string())

        logger.info("Email sent successfully: %s", msg["Subject"])
