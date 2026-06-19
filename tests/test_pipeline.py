#!/usr/bin/env python3
"""
Local end-to-end test for the Saurabh Labs Intelligence System.

Runs every stage with live APIs and prints a clear PASS/FAIL per stage.
Usage:
    python tests/test_pipeline.py [morning|evening|geo|all]

By default runs "morning" only (fastest). Pass "all" to test all three pipelines.
"""
import io
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Force UTF-8 output on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

# ─── ANSI colours ────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg: str) -> None:  print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg: str) -> None: print(f"  {RED}✗{RESET} {msg}")
def warn(msg: str) -> None: print(f"  {YELLOW}⚠{RESET} {msg}")
def info(msg: str) -> None: print(f"  {CYAN}→{RESET} {msg}")
def header(msg: str) -> None: print(f"\n{BOLD}{CYAN}{'─'*60}{RESET}\n{BOLD}  {msg}{RESET}\n{'─'*60}")


# ─── Individual test stages ──────────────────────────────────────────────────

def test_env() -> bool:
    header("STAGE 1 — Environment Variables")
    required = ["OPENAI_API_KEY", "NOTION_API_KEY", "NOTION_DATABASE_ID",
                "EMAIL_ADDRESS", "EMAIL_PASSWORD"]
    optional = ["EMAIL_RECIPIENT", "SMTP_SERVER", "SMTP_PORT", "PRODUCT_HUNT_API_TOKEN"]
    passed = True
    for k in required:
        v = os.getenv(k)
        if v:
            ok(f"{k} = {v[:8]}...")
        else:
            fail(f"{k} is NOT set")
            passed = False
    for k in optional:
        v = os.getenv(k)
        if v:
            ok(f"{k} = {v[:8]}... (optional)")
        else:
            warn(f"{k} not set (optional)")
    return passed


def test_imports() -> bool:
    header("STAGE 2 — Imports")
    modules = [
        ("openai", "openai"),
        ("requests", "requests"),
        ("bs4", "beautifulsoup4"),
        ("dotenv", "python-dotenv"),
        ("markdown", "markdown"),
        ("lxml", "lxml"),
    ]
    passed = True
    for mod, pkg in modules:
        try:
            __import__(mod)
            ok(f"{pkg}")
        except ImportError as exc:
            fail(f"{pkg}: {exc}")
            passed = False
    # Project imports
    for name in [
        "src.utils.logger", "src.utils.retry",
        "src.collectors.hackernews", "src.collectors.github_trending",
        "src.collectors.reddit_collector", "src.collectors.arxiv_collector",
        "src.collectors.news_collector", "src.collectors.product_hunt",
        "src.analyzers.base_analyzer", "src.analyzers.morning_analyzer",
        "src.analyzers.evening_analyzer", "src.analyzers.geo_analyzer",
        "src.emailer.email_sender", "src.notion.notion_client",
    ]:
        try:
            __import__(name)
            ok(name)
        except Exception as exc:
            fail(f"{name}: {exc}")
            passed = False
    return passed


def test_collectors() -> Tuple[bool, Dict[str, Any]]:
    header("STAGE 3 — Data Collectors (live)")
    from src.collectors.hackernews import HackerNewsCollector
    from src.collectors.github_trending import GitHubTrendingCollector
    from src.collectors.reddit_collector import RedditCollector
    from src.collectors.arxiv_collector import ArxivCollector
    from src.collectors.news_collector import NewsCollector

    data: Dict[str, Any] = {}
    passed = True

    stages = [
        ("Hacker News",    lambda: HackerNewsCollector(hours_back=36).collect()),
        ("GitHub Trending",lambda: GitHubTrendingCollector().collect()),
        ("Reddit AI",      lambda: RedditCollector(limit=3).collect(mode="ai")),
        ("arXiv",          lambda: ArxivCollector(max_results=5).collect()),
        ("RSS News",       lambda: NewsCollector(hours_back=36).collect(mode="ai")),
    ]
    for name, fn in stages:
        try:
            t0 = time.time()
            result = fn()
            elapsed = time.time() - t0
            data[name] = result
            # Quick sanity check — result should be a non-empty dict
            total_items = sum(len(v) if isinstance(v, list) else 1 for v in result.values())
            ok(f"{name}: {total_items} items in {elapsed:.1f}s")
        except Exception as exc:
            fail(f"{name}: {exc}")
            data[name] = {}
            passed = False

    return passed, data


def test_openai(data: Dict[str, Any], report_type: str = "morning") -> Tuple[bool, str]:
    header(f"STAGE 4 — OpenAI Generation ({report_type})")
    try:
        import json
        import openai

        api_key = os.getenv("OPENAI_API_KEY")
        client = openai.OpenAI(api_key=api_key)

        # Load the actual prompt
        prompt_path = PROJECT_ROOT / "prompts" / f"{report_type}_prompt.md"
        system_prompt = prompt_path.read_text(encoding="utf-8")

        sample_data = json.dumps(
            {k: (v if not isinstance(v, dict) else dict(list(v.items())[:2])) for k, v in list(data.items())[:3]},
            default=str, indent=2
        )[:4000]

        info("Calling gpt-4o (this may take 30–120s)...")
        t0 = time.time()
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=2000,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Sample data for testing:\n{sample_data}\n\nGenerate a SHORT test version of the report (max 500 words) to confirm the system works."},
            ],
        )
        report = response.choices[0].message.content
        elapsed = time.time() - t0
        ok(f"OpenAI responded in {elapsed:.1f}s ({len(report)} chars)")
        info(f"Preview: {report[:200].strip()}...")
        return True, report
    except Exception as exc:
        fail(f"OpenAI call failed: {exc}")
        traceback.print_exc()
        return False, ""


def test_email_build(report: str, report_type: str = "morning") -> bool:
    header("STAGE 5 — Email Build (dry-run, no send)")
    try:
        from src.emailer.email_sender import EmailSender
        sender = EmailSender()
        msg = sender._build_email(report_type, report, "2026-06-19")
        ok(f"Subject: {msg['Subject']}")
        ok(f"HTML body built ({len(msg.as_string())} bytes)")
        return True
    except Exception as exc:
        fail(f"Email build failed: {exc}")
        traceback.print_exc()
        return False


def test_notion_connection() -> bool:
    header("STAGE 6 — Notion Connection")
    if not os.getenv("NOTION_API_KEY") or not os.getenv("NOTION_DATABASE_ID"):
        warn("Notion credentials not set — skipping")
        return True
    try:
        import requests
        headers = {
            "Authorization": f"Bearer {os.getenv('NOTION_API_KEY')}",
            "Notion-Version": "2022-06-28",
        }
        db_id = os.getenv("NOTION_DATABASE_ID")
        resp = requests.get(f"https://api.notion.com/v1/databases/{db_id}", headers=headers, timeout=15)
        resp.raise_for_status()
        db = resp.json()
        ok(f"Database found: {db.get('title', [{}])[0].get('plain_text', db_id)}")
        props = list(db.get("properties", {}).keys())
        ok(f"Properties: {', '.join(props)}")
        required_props = {"Name", "Date", "Category", "Summary", "Video Ideas", "Status"}
        missing = required_props - set(props)
        if missing:
            warn(f"Missing expected properties: {missing} — add them to the database")
        return True
    except Exception as exc:
        fail(f"Notion connection failed: {exc}")
        return False


def test_report_save(report: str, report_type: str = "morning") -> bool:
    header("STAGE 7 — Save Report to Disk")
    try:
        reports_dir = PROJECT_ROOT / "reports"
        reports_dir.mkdir(exist_ok=True)
        path = reports_dir / f"TEST_{report_type}_2026-06-19.md"
        path.write_text(report, encoding="utf-8")
        ok(f"Saved: {path}")
        ok(f"Size: {path.stat().st_size} bytes")
        return True
    except Exception as exc:
        fail(f"Save failed: {exc}")
        return False


# ─── Main ────────────────────────────────────────────────────────────────────

def run_test(pipeline: str = "morning") -> None:
    print(f"\n{BOLD}{'═'*60}")
    print(f"  SAURABH LABS INTELLIGENCE — END-TO-END TEST")
    print(f"  Pipeline: {pipeline.upper()}")
    print(f"{'═'*60}{RESET}")

    results: List[Tuple[str, bool]] = []

    # Stage 1 — env
    r = test_env()
    results.append(("Environment", r))
    if not r:
        print(f"\n{RED}Fatal: missing required env vars. Fix .env and retry.{RESET}")
        sys.exit(1)

    # Stage 2 — imports
    r = test_imports()
    results.append(("Imports", r))
    if not r:
        print(f"\n{RED}Fatal: import errors. Run: pip install -r requirements.txt{RESET}")
        sys.exit(1)

    # Stage 3 — collectors
    r, data = test_collectors()
    results.append(("Collectors", r))

    # Stage 4 — OpenAI
    r, report = test_openai(data, pipeline)
    results.append(("OpenAI generation", r))
    if not r:
        report = "# Test Report\n\nOpenAI call failed — using placeholder for downstream tests."

    # Stage 5 — email build
    r = test_email_build(report, pipeline)
    results.append(("Email build", r))

    # Stage 6 — Notion connection
    r = test_notion_connection()
    results.append(("Notion connection", r))

    # Stage 7 — file save
    r = test_report_save(report, pipeline)
    results.append(("Report save", r))

    # Summary
    header("SUMMARY")
    all_pass = True
    for stage, passed in results:
        if passed:
            ok(stage)
        else:
            fail(stage)
            all_pass = False

    print()
    if all_pass:
        print(f"{GREEN}{BOLD}✓ ALL STAGES PASSED — system is ready!{RESET}")
        print(f"  Run the full pipeline with:  python scripts/run_{pipeline}.py")
    else:
        print(f"{RED}{BOLD}✗ Some stages failed — review errors above.{RESET}")
    print()


if __name__ == "__main__":
    pipeline = sys.argv[1] if len(sys.argv) > 1 else "morning"
    valid = {"morning", "evening", "geo", "all"}
    if pipeline not in valid:
        print(f"Usage: python tests/test_pipeline.py [morning|evening|geo|all]")
        sys.exit(1)

    if pipeline == "all":
        for p in ["morning", "evening", "geo"]:
            run_test(p)
    else:
        run_test(pipeline)
