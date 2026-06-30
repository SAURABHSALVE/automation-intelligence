# """Notion API integration — saves reports to a Notion database."""
# import os
# import re
# from datetime import datetime
# from typing import Any, Dict, List, Optional

# import requests

# from src.utils.logger import setup_logger
# from src.utils.retry import retry

# logger = setup_logger(__name__)

# NOTION_API = "https://api.notion.com/v1"
# NOTION_VERSION = "2022-06-28"
# MAX_RICH_TEXT = 1990   # Notion hard limit is 2000; stay safely under

# CATEGORY_MAP = {
#     "morning": "Morning AI",
#     "evening": "Evening Tech",
#     "geo": "GeoPolitics",
#     "space": "Space & Science",
# }


# class NotionReportSaver:
#     def __init__(self) -> None:
#         self.token = os.environ["NOTION_API_KEY"]
#         self.database_id = os.environ["NOTION_DATABASE_ID"]
#         self._headers = {
#             "Authorization": f"Bearer {self.token}",
#             "Content-Type": "application/json",
#             "Notion-Version": NOTION_VERSION,
#         }

#     def _post(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
#         resp = requests.post(f"{NOTION_API}/{endpoint}", json=payload, headers=self._headers, timeout=30)
#         if not resp.ok:
#             logger.error("Notion POST %s → %d: %s", endpoint, resp.status_code, resp.text[:500])
#         resp.raise_for_status()
#         return resp.json()

#     def _patch(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
#         resp = requests.patch(f"{NOTION_API}/{endpoint}", json=payload, headers=self._headers, timeout=30)
#         resp.raise_for_status()
#         return resp.json()

#     @retry(max_attempts=3, delay=2.0, exceptions=(requests.HTTPError, requests.ConnectionError))
#     def _post_retry(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
#         return self._post(endpoint, payload)

#     def save_report(self, report_type: str, report_md: str, date_str: Optional[str] = None) -> str:
#         if date_str is None:
#             date_str = datetime.now().strftime("%Y-%m-%d")

#         category = CATEGORY_MAP.get(report_type, "Intelligence Report")
#         summary = self._extract_summary(report_md)
#         video_ideas = self._extract_video_ideas(report_md)
#         title = f"{category} — {date_str}"

#         logger.info("Creating Notion page: %s", title)

#         # Try full property set; fall back to minimal if DB schema differs
#         try:
#             page = self._create_page(title, date_str, category, summary, video_ideas, report_md)
#         except Exception as exc:
#             logger.warning("Full property creation failed (%s) — retrying with minimal", exc)
#             page = self._create_page_minimal(title, date_str)

#         page_id = page["id"]
#         page_url = page.get("url", f"https://notion.so/{page_id.replace('-', '')}")
#         logger.info("Page created: %s", page_url)

#         self._append_content_blocks(page_id, report_md)
#         return page_url

#     def _create_page(
#         self,
#         title: str,
#         date_str: str,
#         category: str,
#         summary: str,
#         video_ideas: str,
#         report_md: str = "",
#     ) -> Dict[str, Any]:
#         payload: Dict[str, Any] = {
#             "parent": {"database_id": self.database_id},
#             "properties": {
#                 "Name": {"title": [{"text": {"content": self._safe(title)}}]},
#                 "Date": {"date": {"start": date_str}},
#                 "Category": {"select": {"name": category}},
#                 "Summary": {"rich_text": [{"text": {"content": self._safe(summary)}}]},
#                 "Video Ideas": {"rich_text": [{"text": {"content": self._safe(video_ideas)}}]},
#                 "Markdown Report": {"rich_text": [{"text": {"content": self._safe(report_md)}}]},
#                 "Status": {"select": {"name": "Published"}},
#             },
#         }
#         return self._post_retry("pages", payload)

#     def _create_page_minimal(self, title: str, date_str: str) -> Dict[str, Any]:
#         payload: Dict[str, Any] = {
#             "parent": {"database_id": self.database_id},
#             "properties": {
#                 "Name": {"title": [{"text": {"content": self._safe(title)}}]},
#                 "Date": {"date": {"start": date_str}},
#             },
#         }
#         return self._post_retry("pages", payload)

#     @retry(max_attempts=3, delay=2.0, exceptions=(requests.HTTPError, requests.ConnectionError))
#     def _patch_retry(self, endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
#         resp = requests.patch(f"{NOTION_API}/{endpoint}", json=payload, headers=self._headers, timeout=30)
#         if not resp.ok:
#             logger.error("Notion PATCH %s → %d: %s", endpoint, resp.status_code, resp.text[:500])
#         resp.raise_for_status()
#         return resp.json()

#     def _append_content_blocks(self, page_id: str, report_md: str) -> None:
#         blocks = self._md_to_blocks(report_md)
#         chunk_size = 50
#         for i in range(0, len(blocks), chunk_size):
#             chunk = blocks[i: i + chunk_size]
#             try:
#                 # Notion append-block-children is PATCH, not POST
#                 self._patch_retry(f"blocks/{page_id}/children", {"children": chunk})
#             except Exception as exc:
#                 logger.warning("Block chunk %d-%d failed: %s — skipping", i, i + chunk_size, exc)

#     @staticmethod
#     def _safe(text: str, limit: int = MAX_RICH_TEXT) -> str:
#         """Truncate and strip null bytes that Notion rejects."""
#         return (text or "").replace("\x00", "").strip()[:limit]

#     @staticmethod
#     def _parse_inline(text: str) -> List[Dict[str, Any]]:
#         """Parse inline markdown into Notion rich_text with bold/italic/code annotations."""
#         text = (text or "").replace("\x00", "").strip()[:MAX_RICH_TEXT]
#         if not text:
#             return [{"type": "text", "text": {"content": ""}}]

#         # Order matters: bold+italic first, then bold, then code, strikethrough, italic
#         pattern = re.compile(
#             r'\*\*\*(.+?)\*\*\*'   # bold+italic
#             r'|\*\*(.+?)\*\*'       # bold
#             r'|`(.+?)`'             # inline code
#             r'|~~(.+?)~~'           # strikethrough
#             r'|\*(.+?)\*'           # italic
#         )

#         segments: List[Dict[str, Any]] = []
#         last = 0
#         for m in pattern.finditer(text):
#             if m.start() > last:
#                 segments.append({"type": "text", "text": {"content": text[last:m.start()]}})
#             bold_italic, bold, code, strike, italic = (
#                 m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
#             )
#             if bold_italic:
#                 segments.append({"type": "text", "text": {"content": bold_italic},
#                                   "annotations": {"bold": True, "italic": True}})
#             elif bold:
#                 segments.append({"type": "text", "text": {"content": bold},
#                                   "annotations": {"bold": True}})
#             elif code:
#                 segments.append({"type": "text", "text": {"content": code},
#                                   "annotations": {"code": True}})
#             elif strike:
#                 segments.append({"type": "text", "text": {"content": strike},
#                                   "annotations": {"strikethrough": True}})
#             elif italic:
#                 segments.append({"type": "text", "text": {"content": italic},
#                                   "annotations": {"italic": True}})
#             last = m.end()
#         if last < len(text):
#             segments.append({"type": "text", "text": {"content": text[last:]}})
#         return segments or [{"type": "text", "text": {"content": text}}]

#     @classmethod
#     def _rt(cls, content: str) -> List[Dict[str, Any]]:
#         return cls._parse_inline(content)

#     # Emoji prefixes that signal a callout block
#     _CALLOUT_EMOJIS = {
#         "🔴": "red", "🚨": "red", "⚠️": "orange",
#         "🚀": "blue", "💡": "yellow", "🌐": "blue",
#         "💰": "green", "📊": "purple", "🔭": "gray",
#         "🎬": "pink", "🌍": "green", "⚡": "yellow",
#         "🧠": "purple", "📰": "default", "🔥": "orange",
#     }

#     def _md_to_blocks(self, md_text: str) -> List[Dict[str, Any]]:
#         blocks: List[Dict[str, Any]] = []
#         prev_was_h1 = False

#         for line in md_text.split("\n"):
#             s = line.rstrip()

#             if not s:
#                 prev_was_h1 = False
#                 continue

#             # H1 — add divider before each major section (except the first)
#             if s.startswith("# "):
#                 if blocks and blocks[-1].get("type") != "divider":
#                     blocks.append({"object": "block", "type": "divider", "divider": {}})
#                 blocks.append({
#                     "object": "block", "type": "heading_1",
#                     "heading_1": {
#                         "rich_text": self._rt(s[2:]),
#                         "color": "purple_background",
#                         "is_toggleable": False,
#                     },
#                 })
#                 prev_was_h1 = True
#                 continue

#             # H2 — colored heading
#             if s.startswith("## "):
#                 blocks.append({
#                     "object": "block", "type": "heading_2",
#                     "heading_2": {
#                         "rich_text": self._rt(s[3:]),
#                         "color": "blue",
#                         "is_toggleable": False,
#                     },
#                 })
#                 prev_was_h1 = False
#                 continue

#             # H3
#             if s.startswith("### "):
#                 blocks.append({
#                     "object": "block", "type": "heading_3",
#                     "heading_3": {"rich_text": self._rt(s[4:])},
#                 })
#                 prev_was_h1 = False
#                 continue

#             # Bullet list
#             if s.startswith("- ") or s.startswith("* "):
#                 blocks.append({"object": "block", "type": "bulleted_list_item",
#                                 "bulleted_list_item": {"rich_text": self._rt(s[2:])}})
#                 prev_was_h1 = False
#                 continue

#             # Numbered list
#             if re.match(r"^\d+\. ", s):
#                 content = re.sub(r"^\d+\. ", "", s)
#                 blocks.append({"object": "block", "type": "numbered_list_item",
#                                 "numbered_list_item": {"rich_text": self._rt(content)}})
#                 prev_was_h1 = False
#                 continue

#             # Blockquote
#             if s.startswith("> "):
#                 blocks.append({"object": "block", "type": "quote",
#                                 "quote": {"rich_text": self._rt(s[2:])}})
#                 prev_was_h1 = False
#                 continue

#             # Explicit divider — skip consecutive duplicates
#             if s.startswith("---") or s.startswith("***"):
#                 if not blocks or blocks[-1].get("type") != "divider":
#                     blocks.append({"object": "block", "type": "divider", "divider": {}})
#                 prev_was_h1 = False
#                 continue

#             # Callout: paragraph that starts with a known emoji
#             matched_emoji = next(
#                 (e for e in self._CALLOUT_EMOJIS if s.startswith(e)), None
#             )
#             if matched_emoji:
#                 color = self._CALLOUT_EMOJIS[matched_emoji]
#                 blocks.append({
#                     "object": "block", "type": "callout",
#                     "callout": {
#                         "rich_text": self._rt(s),
#                         "icon": {"type": "emoji", "emoji": matched_emoji},
#                         "color": f"{color}_background",
#                     },
#                 })
#                 prev_was_h1 = False
#                 continue

#             # Regular paragraph
#             blocks.append({"object": "block", "type": "paragraph",
#                             "paragraph": {"rich_text": self._rt(s)}})
#             prev_was_h1 = False

#         return blocks

#     @staticmethod
#     def _extract_summary(md_text: str) -> str:
#         lines = md_text.split("\n")
#         for i, line in enumerate(lines):
#             if line.startswith("# "):
#                 for j in range(i + 1, min(i + 6, len(lines))):
#                     if lines[j].strip():
#                         return lines[j].strip()[:500]
#         return md_text[:500]

#     @staticmethod
#     def _extract_video_ideas(md_text: str) -> str:
#         ideas: List[str] = []
#         in_section = False
#         for line in md_text.split("\n"):
#             if "video" in line.lower() and line.startswith("#"):
#                 in_section = True
#                 continue
#             if in_section:
#                 if line.startswith("#") and "video" not in line.lower():
#                     break
#                 if line.strip():
#                     ideas.append(line.strip())
#         return "\n".join(ideas[:20])
