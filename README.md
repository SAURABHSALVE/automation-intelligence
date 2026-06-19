# Saurabh Labs Intelligence System

Fully automated intelligence platform for content creation and research. Generates 3 daily reports using Claude AI, saves them to Notion, and delivers beautiful HTML emails — all via GitHub Actions. No paid tools, no n8n.

---

## What It Does

| Report | Schedule (IST) | Coverage |
|--------|---------------|----------|
| Morning Intelligence | 7:00 AM | AI, LLMs, GitHub Trending, HN, arXiv, Product Hunt, Reddit |
| Evening Tech Brief | 9:00 PM | Startups, launches, consumer tech, hardware, viral opportunities |
| Geo & History Brief | 9:30 PM | Geopolitics, history, science, fascinating facts |

Each run:
1. Collects data from free APIs (no paid subscriptions)
2. Sends everything to Claude for deep analysis
3. Saves the Markdown report to `reports/`
4. Posts the report as a Notion page
5. Sends a beautiful HTML email

---

## Setup

### 1. Clone & install

```bash
git clone https://github.com/YOUR_USERNAME/saurabh-intelligence.git
cd saurabh-intelligence
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your real keys
```

Required keys:

| Key | Where to get it |
|-----|----------------|
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com) |
| `NOTION_API_KEY` | [notion.so/my-integrations](https://www.notion.so/my-integrations) |
| `NOTION_DATABASE_ID` | From the URL of your Notion database |
| `EMAIL_ADDRESS` | Your Gmail address |
| `EMAIL_PASSWORD` | Gmail App Password (not your real password) |
| `EMAIL_RECIPIENT` | Who gets the emails |

### 3. Create Gmail App Password

1. Go to your Google Account → Security → 2-Step Verification → App passwords
2. Select "Mail" and generate a 16-character password
3. Use that password as `EMAIL_PASSWORD`

### 4. Create Notion Database

Create a new Notion database with these exact properties:

| Property | Type |
|----------|------|
| Name | Title |
| Date | Date |
| Category | Select |
| Summary | Text |
| Video Ideas | Text |
| Status | Select |

Share the database with your integration (click Share → invite your integration).

### 5. Test locally

```bash
python scripts/run_morning.py
python scripts/run_evening.py
python scripts/run_geo.py
```

---

## GitHub Actions Setup

### Add Secrets

Go to your GitHub repo → Settings → Secrets and variables → Actions → New repository secret.

Add all keys from `.env.example` as secrets.

### Enable Workflows

Push to GitHub. The workflows in `.github/workflows/` will run automatically on schedule. You can also trigger them manually from the Actions tab.

---

## Project Structure

```
saurabh-intelligence/
├── reports/                    # Generated Markdown reports
├── prompts/
│   ├── morning_prompt.md       # Claude system prompt for morning report
│   ├── evening_prompt.md       # Claude system prompt for evening report
│   └── geo_prompt.md           # Claude system prompt for geo report
├── src/
│   ├── collectors/             # Data collection from APIs
│   │   ├── hackernews.py       # HN Algolia API
│   │   ├── github_trending.py  # GitHub trending + search
│   │   ├── reddit_collector.py # Reddit public JSON API
│   │   ├── arxiv_collector.py  # arXiv Atom feed
│   │   ├── product_hunt.py     # Product Hunt GraphQL API
│   │   └── news_collector.py   # RSS feeds (TechCrunch, Verge, BBC, etc.)
│   ├── analyzers/              # Claude-powered analysis
│   │   ├── base_analyzer.py    # Shared Claude API client
│   │   ├── morning_analyzer.py
│   │   ├── evening_analyzer.py
│   │   └── geo_analyzer.py
│   ├── emailer/
│   │   └── email_sender.py     # Gmail SMTP sender
│   ├── notion/
│   │   └── notion_client.py    # Notion API integration
│   ├── utils/
│   │   ├── logger.py           # Structured logging
│   │   └── retry.py            # Exponential backoff decorator
│   └── templates/              # HTML email templates
│       ├── morning_email.html
│       ├── evening_email.html
│       └── geo_email.html
├── scripts/
│   ├── run_morning.py          # Morning pipeline runner
│   ├── run_evening.py          # Evening pipeline runner
│   └── run_geo.py              # Geo pipeline runner
├── .github/workflows/
│   ├── morning.yml             # Cron: 7 AM IST
│   ├── evening.yml             # Cron: 9 PM IST
│   └── geo.yml                 # Cron: 9:30 PM IST
├── requirements.txt
├── .env.example
└── README.md
```

---

## Data Sources (All Free)

| Source | API | Key Required? |
|--------|-----|--------------|
| Hacker News | Algolia HN API | No |
| GitHub Trending | Web scrape + GitHub search API | No |
| Reddit | Public JSON API | No |
| arXiv | Atom feed API | No |
| Product Hunt | GraphQL API | Optional |
| TechCrunch, The Verge, VentureBeat | RSS feeds | No |
| BBC, Reuters, Al Jazeera | RSS feeds | No |

---

## Customization

**Change report schedule**: Edit the `cron:` lines in `.github/workflows/*.yml`. [Cron syntax reference](https://crontab.guru/).

**Change Claude model**: Edit `MODEL` in `src/analyzers/base_analyzer.py`.

**Add new data sources**: Create a new collector in `src/collectors/`, inherit nothing, implement a `collect()` method that returns a dict.

**Change email recipients**: Set `EMAIL_RECIPIENT` in `.env` or GitHub Secrets.

**Edit prompts**: Modify files in `prompts/` — no code changes needed.

---

## Cost Estimate

Each report costs approximately **$0.10–0.30** in Claude API usage (using claude-opus-4-8).  
3 reports/day × 30 days ≈ **$9–27/month** depending on data volume.
