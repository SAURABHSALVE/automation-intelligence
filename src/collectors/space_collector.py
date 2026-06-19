"""Space, Physics & Science data collector — NASA, SpaceX, arXiv, ISS, and more."""
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests

from src.utils.logger import setup_logger
from src.utils.retry import retry

logger = setup_logger(__name__)

NASA_KEY = os.getenv("NASA_API_KEY", "DEMO_KEY")

HEADERS = {"User-Agent": "saurabh-labs-intelligence/1.0 (science collector)"}

SPACE_RSS_FEEDS = [
    ("Space.com", "https://www.space.com/feeds/all"),
    ("Universe Today", "https://www.universetoday.com/feed/"),
    ("Spaceflight Now", "https://spaceflightnow.com/feed/"),
    ("Sky & Telescope", "https://skyandtelescope.org/astronomy-news/feed/"),
    ("EarthSky", "https://earthsky.org/feed/"),
    ("Planetary Society", "https://www.planetary.org/articles/rss"),
    ("Phys.org", "https://phys.org/rss-feed/"),
    ("ScienceDaily Space", "https://www.sciencedaily.com/rss/space_time/space_exploration.xml"),
    ("ScienceDaily Physics", "https://www.sciencedaily.com/rss/matter_energy/physics.xml"),
    ("Quanta Magazine", "https://www.quantamagazine.org/feed/"),
    ("New Scientist Physics", "https://www.newscientist.com/subject/physics/feed/"),
    ("NASA Breaking News", "https://www.nasa.gov/rss/dyn/breaking_news.rss"),
    ("ESA Space Science", "https://www.esa.int/rssfeed/Our_Activities/Space_Science"),
]

ARXIV_RSS_FEEDS = [
    ("arXiv Astrophysics", "https://export.arxiv.org/rss/astro-ph"),
    ("arXiv Physics", "https://export.arxiv.org/rss/physics"),
    ("arXiv Quantum Physics", "https://export.arxiv.org/rss/quant-ph"),
]

YOUTUBE_SCIENCE_FEEDS = [
    ("Kurzgesagt", "https://www.youtube.com/feeds/videos.xml?channel_id=UCsXVk37biltHxV1v3H_4aaw"),
    ("Veritasium", "https://www.youtube.com/feeds/videos.xml?channel_id=UCHnyfMqiRRG1u-2MsSQLbXA"),
    ("PBS Space Time", "https://www.youtube.com/feeds/videos.xml?channel_id=UC7_gcs09iThXybpVgjHZ_7g"),
    ("SciShow Space", "https://www.youtube.com/feeds/videos.xml?channel_id=UCrMePiHCWG4Vwqv3t7W9EFg"),
]


class SpaceCollector:
    def __init__(self, limit: int = 10) -> None:
        self.limit = limit

    # ── RSS helpers ─────────────────────────────────────────────────────────

    @retry(max_attempts=2, delay=2.0, exceptions=(requests.ConnectionError, requests.Timeout))
    def _fetch_rss(self, name: str, url: str, max_items: int = 12) -> List[Dict[str, Any]]:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 429:
            logger.warning("RSS %s rate-limited — skipping", name)
            return []
        resp.raise_for_status()
        return self._parse_rss(name, resp.text, max_items)

    @staticmethod
    def _parse_rss(source: str, xml_text: str, max_items: int = 12) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return items
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "media": "http://search.yahoo.com/mrss/",
        }
        for el in root.iter("item"):
            if len(items) >= max_items:
                break
            title = (el.findtext("title") or "").strip()
            link = (el.findtext("link") or "").strip()
            desc = (el.findtext("description") or "")[:500].strip()
            pub = (el.findtext("pubDate") or "").strip()
            items.append({"source": source, "title": title, "url": link, "summary": desc, "published": pub})
        for entry in root.findall(".//atom:entry", ns):
            if len(items) >= max_items:
                break
            title_el = entry.find("atom:title", ns)
            link_el = entry.find("atom:link", ns)
            summary_el = entry.find("atom:summary", ns)
            pub_el = entry.find("atom:published", ns) or entry.find("atom:updated", ns)
            title = (title_el.text or "").strip() if title_el is not None else ""
            link = link_el.get("href", "") if link_el is not None else ""
            summary = (summary_el.text or "")[:500].strip() if summary_el is not None else ""
            pub = pub_el.text if pub_el is not None else ""
            items.append({"source": source, "title": title, "url": link, "summary": summary, "published": pub})
        return items

    def _collect_rss_batch(self, feeds: List[tuple], max_each: int = 10) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        for name, url in feeds:
            try:
                items = self._fetch_rss(name, url, max_items=max_each)
                results.extend(items)
                time.sleep(0.5)
            except Exception as exc:
                logger.warning("RSS '%s' failed: %s", name, exc)
        return results

    # ── NASA APIs ────────────────────────────────────────────────────────────

    def _nasa_apod(self) -> Dict[str, Any]:
        try:
            resp = requests.get(
                "https://api.nasa.gov/planetary/apod",
                params={"api_key": NASA_KEY},
                headers=HEADERS, timeout=15,
            )
            resp.raise_for_status()
            d = resp.json()
            return {
                "title": d.get("title"),
                "date": d.get("date"),
                "explanation": (d.get("explanation") or "")[:800],
                "url": d.get("url"),
                "media_type": d.get("media_type"),
                "copyright": d.get("copyright"),
            }
        except Exception as exc:
            logger.warning("NASA APOD failed: %s", exc)
            return {}

    def _nasa_neo(self) -> List[Dict[str, Any]]:
        try:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            resp = requests.get(
                "https://api.nasa.gov/neo/rest/v1/feed",
                params={"start_date": today, "end_date": today, "api_key": NASA_KEY},
                headers=HEADERS, timeout=20,
            )
            resp.raise_for_status()
            data = resp.json()
            neos = []
            for neo_list in data.get("near_earth_objects", {}).values():
                for neo in neo_list[:5]:
                    approach = neo.get("close_approach_data", [{}])[0]
                    neos.append({
                        "name": neo.get("name"),
                        "diameter_m": neo.get("estimated_diameter", {}).get("meters", {}).get("estimated_diameter_max"),
                        "hazardous": neo.get("is_potentially_hazardous_asteroid"),
                        "miss_distance_km": approach.get("miss_distance", {}).get("kilometers"),
                        "velocity_kmh": approach.get("relative_velocity", {}).get("kilometers_per_hour"),
                        "close_approach": approach.get("close_approach_date"),
                    })
            return neos[:8]
        except Exception as exc:
            logger.warning("NASA NEO failed: %s", exc)
            return []

    def _mars_rover(self) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(
                "https://api.nasa.gov/mars-photos/api/v1/rovers/curiosity/latest_photos",
                params={"api_key": NASA_KEY},
                headers=HEADERS, timeout=20,
            )
            resp.raise_for_status()
            photos = resp.json().get("latest_photos", [])[:5]
            return [
                {
                    "id": p.get("id"),
                    "sol": p.get("sol"),
                    "earth_date": p.get("earth_date"),
                    "camera": p.get("camera", {}).get("full_name"),
                    "img_src": p.get("img_src"),
                }
                for p in photos
            ]
        except Exception as exc:
            logger.warning("Mars rover photos failed: %s", exc)
            return []

    def _nasa_images(self, query: str = "space nebula galaxy") -> List[Dict[str, Any]]:
        try:
            resp = requests.get(
                "https://images-api.nasa.gov/search",
                params={"q": query, "media_type": "image", "page_size": 5},
                headers=HEADERS, timeout=15,
            )
            resp.raise_for_status()
            items = resp.json().get("collection", {}).get("items", [])[:5]
            results = []
            for item in items:
                data_list = item.get("data", [{}])
                d = data_list[0] if data_list else {}
                results.append({
                    "title": d.get("title"),
                    "description": (d.get("description") or "")[:300],
                    "date_created": d.get("date_created"),
                    "nasa_id": d.get("nasa_id"),
                })
            return results
        except Exception as exc:
            logger.warning("NASA images search failed: %s", exc)
            return []

    # ── SpaceX ───────────────────────────────────────────────────────────────

    def _spacex_latest(self) -> Dict[str, Any]:
        try:
            resp = requests.get("https://api.spacexdata.com/v4/launches/latest", headers=HEADERS, timeout=15)
            resp.raise_for_status()
            d = resp.json()
            return {
                "name": d.get("name"),
                "date_utc": d.get("date_utc"),
                "success": d.get("success"),
                "details": (d.get("details") or "")[:400],
                "rocket": d.get("rocket"),
                "flight_number": d.get("flight_number"),
            }
        except Exception as exc:
            logger.warning("SpaceX latest launch failed: %s", exc)
            return {}

    def _spacex_upcoming(self) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(
                "https://api.spacexdata.com/v4/launches/upcoming",
                headers=HEADERS, timeout=15,
            )
            resp.raise_for_status()
            launches = resp.json()[:5]
            return [
                {
                    "name": l.get("name"),
                    "date_utc": l.get("date_utc"),
                    "details": (l.get("details") or "")[:300],
                    "flight_number": l.get("flight_number"),
                }
                for l in launches
            ]
        except Exception as exc:
            logger.warning("SpaceX upcoming failed: %s", exc)
            return []

    # ── ISS ──────────────────────────────────────────────────────────────────

    def _iss_position(self) -> Dict[str, Any]:
        try:
            resp = requests.get("http://api.open-notify.org/iss-now.json", timeout=10)
            resp.raise_for_status()
            d = resp.json()
            return {
                "latitude": d.get("iss_position", {}).get("latitude"),
                "longitude": d.get("iss_position", {}).get("longitude"),
                "timestamp": d.get("timestamp"),
            }
        except Exception as exc:
            logger.warning("ISS position failed: %s", exc)
            return {}

    def _iss_astronauts(self) -> List[Dict[str, Any]]:
        try:
            resp = requests.get("http://api.open-notify.org/astros.json", timeout=10)
            resp.raise_for_status()
            d = resp.json()
            return d.get("people", [])
        except Exception as exc:
            logger.warning("ISS astronauts failed: %s", exc)
            return []

    # ── arXiv papers ─────────────────────────────────────────────────────────

    def _arxiv_papers(self) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(
                "https://export.arxiv.org/api/query",
                params={
                    "search_query": "cat:astro-ph OR cat:quant-ph OR cat:physics.pop-ph",
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                    "max_results": 12,
                },
                headers=HEADERS, timeout=20,
            )
            resp.raise_for_status()
            ns = {"atom": "http://www.w3.org/2005/Atom"}
            root = ET.fromstring(resp.text)
            papers = []
            for entry in root.findall("atom:entry", ns):
                title_el = entry.find("atom:title", ns)
                summary_el = entry.find("atom:summary", ns)
                pub_el = entry.find("atom:published", ns)
                link_el = entry.find("atom:link[@type='text/html']", ns)
                authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns) if a.find("atom:name", ns) is not None]
                papers.append({
                    "title": (title_el.text or "").strip() if title_el is not None else "",
                    "abstract": (summary_el.text or "")[:500].strip() if summary_el is not None else "",
                    "published": pub_el.text if pub_el is not None else "",
                    "url": link_el.get("href", "") if link_el is not None else "",
                    "authors": authors[:3],
                })
            return papers
        except Exception as exc:
            logger.warning("arXiv API failed: %s", exc)
            return []

    # ── Upcoming launches (Space Launch Library) ──────────────────────────────

    def _upcoming_launches(self) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(
                "https://ll.thespacedevs.com/2.2.0/launch/upcoming/",
                params={"limit": 5, "format": "json"},
                headers=HEADERS, timeout=20,
            )
            if resp.status_code == 429:
                logger.warning("Space Launch Library rate-limited — skipping")
                return []
            resp.raise_for_status()
            results = resp.json().get("results", [])
            return [
                {
                    "name": l.get("name"),
                    "net": l.get("net"),
                    "status": l.get("status", {}).get("name"),
                    "rocket": l.get("rocket", {}).get("configuration", {}).get("name"),
                    "mission": (l.get("mission", {}) or {}).get("description", "")[:300],
                    "launch_service_provider": l.get("launch_service_provider", {}).get("name"),
                }
                for l in results
            ]
        except Exception as exc:
            logger.warning("Space Launch Library failed: %s", exc)
            return []

    # ── JPL close approaches ─────────────────────────────────────────────────

    def _jpl_close_approaches(self) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(
                "https://ssd-api.jpl.nasa.gov/cad.api",
                params={"dist-max": "0.05", "date-min": "today", "limit": 5},
                headers=HEADERS, timeout=15,
            )
            resp.raise_for_status()
            d = resp.json()
            fields = d.get("fields", [])
            data = d.get("data", [])
            return [dict(zip(fields, row)) for row in data]
        except Exception as exc:
            logger.warning("JPL close approaches failed: %s", exc)
            return []

    # ── NOAA solar wind ───────────────────────────────────────────────────────

    def _solar_wind(self) -> Dict[str, Any]:
        try:
            resp = requests.get(
                "https://services.swpc.noaa.gov/products/summary/solar-wind-speed.json",
                headers=HEADERS, timeout=10,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("NOAA solar wind failed: %s", exc)
            return {}

    # ── Exoplanet archive ─────────────────────────────────────────────────────

    def _recent_exoplanets(self) -> List[Dict[str, Any]]:
        try:
            resp = requests.get(
                "https://exoplanetarchive.ipac.caltech.edu/TAP/sync",
                params={
                    "query": "select top 5 pl_name,disc_year,pl_orbper,pl_rade,disc_facility from pscomppars order by disc_year desc",
                    "format": "json",
                },
                headers=HEADERS, timeout=20,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("Exoplanet archive failed: %s", exc)
            return []

    # ── Main collection ───────────────────────────────────────────────────────

    def collect(self) -> Dict[str, Any]:
        logger.info("=== Collecting Space & Science intelligence data ===")

        data: Dict[str, Any] = {
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

        logger.info("Fetching NASA APOD...")
        data["nasa_apod"] = self._nasa_apod()

        logger.info("Fetching NASA NEO (near-Earth objects)...")
        data["near_earth_objects"] = self._nasa_neo()

        logger.info("Fetching Mars Curiosity rover photos...")
        data["mars_rover_photos"] = self._mars_rover()

        logger.info("Fetching NASA image highlights...")
        data["nasa_images"] = self._nasa_images()

        logger.info("Fetching SpaceX launches...")
        data["spacex_latest_launch"] = self._spacex_latest()
        data["spacex_upcoming_launches"] = self._spacex_upcoming()

        logger.info("Fetching ISS data...")
        data["iss_position"] = self._iss_position()
        data["iss_astronauts"] = self._iss_astronauts()

        logger.info("Fetching space news RSS feeds...")
        data["space_news"] = self._collect_rss_batch(SPACE_RSS_FEEDS, max_each=8)

        logger.info("Fetching arXiv RSS feeds...")
        data["arxiv_rss"] = self._collect_rss_batch(ARXIV_RSS_FEEDS, max_each=6)

        logger.info("Fetching arXiv API papers...")
        data["arxiv_papers"] = self._arxiv_papers()

        logger.info("Fetching YouTube science channel videos...")
        data["youtube_science"] = self._collect_rss_batch(YOUTUBE_SCIENCE_FEEDS, max_each=5)

        logger.info("Fetching upcoming launch schedule...")
        data["upcoming_launches"] = self._upcoming_launches()

        logger.info("Fetching JPL asteroid close approaches...")
        data["asteroid_close_approaches"] = self._jpl_close_approaches()

        logger.info("Fetching NOAA solar wind...")
        data["solar_wind"] = self._solar_wind()

        logger.info("Fetching recent exoplanet discoveries...")
        data["recent_exoplanets"] = self._recent_exoplanets()

        logger.info("Space collection complete.")
        return data
