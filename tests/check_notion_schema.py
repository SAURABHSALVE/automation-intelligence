#!/usr/bin/env python3
"""Inspect Notion database schema and test page creation."""
import os, sys, json, requests
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
os.chdir(Path(__file__).parent.parent)
from dotenv import load_dotenv; load_dotenv(".env")

headers = {
    "Authorization": f"Bearer {os.environ['NOTION_API_KEY']}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}
db_id = os.environ["NOTION_DATABASE_ID"]

resp = requests.get(f"https://api.notion.com/v1/databases/{db_id}", headers=headers)
props = resp.json().get("properties", {})
print("=== Database Properties ===")
for name, val in props.items():
    print(f"  {name!r}: {val['type']}")

# Now test page creation with full payload to see exact error
print("\n=== Testing page creation ===")
payload = {
    "parent": {"database_id": db_id},
    "properties": {
        "Name": {"title": [{"text": {"content": "TEST PAGE — DELETE ME"}}]},
        "Date": {"date": {"start": "2026-06-19"}},
        "Category": {"select": {"name": "Morning Intelligence"}},
        "Summary": {"rich_text": [{"text": {"content": "Test summary"}}]},
        "Video Ideas": {"rich_text": [{"text": {"content": "Test video ideas"}}]},
        "Markdown Report": {"rich_text": [{"text": {"content": "Test report"}}]},
        "Status": {"select": {"name": "Published"}},
    },
}
r = requests.post("https://api.notion.com/v1/pages", json=payload, headers=headers)
print(f"Status: {r.status_code}")
if r.status_code != 200:
    print("Error:", json.dumps(r.json(), indent=2))
else:
    page = r.json()
    print(f"Created page: {page.get('url')}")
    # Clean up
    requests.patch(f"https://api.notion.com/v1/pages/{page['id']}", json={"archived": True}, headers=headers)
    print("Test page archived.")
