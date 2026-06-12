"""
Scraper for ProcyclingStats.com — fetches Grand Tour data.

Data is scraped from public HTML pages (no API key required).
Scraped fields:
  - Race status (not started / live / finished)
  - Current / next stage info
  - GC top 10
  - Stage winner
  - Points / KOM / Youth jersey leaders
"""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

import aiohttp
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)

PCS_BASE = "https://www.procyclingstats.com"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; HomeAssistant/GrandCyclingTours/1.0)"
    )
}


async def fetch_html(session: aiohttp.ClientSession, url: str) -> str | None:
    """Fetch raw HTML from a URL."""
    try:
        async with session.get(url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status == 200:
                return await resp.text()
            _LOGGER.warning("HTTP %s for %s", resp.status, url)
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.error("Fetch error for %s: %s", url, exc)
    return None


def _text(el) -> str:
    return el.get_text(strip=True) if el else ""


def _safe_int(val: str) -> int | None:
    try:
        return int(val.strip().lstrip("+"))
    except (ValueError, AttributeError):
        return None


# ---------------------------------------------------------------------------
# Race overview page
# ---------------------------------------------------------------------------

async def get_race_data(session: aiohttp.ClientSession, race_slug: str, year: int) -> dict[str, Any]:
    """
    Fetch and parse the main race page.
    Returns a dict with stage list, GC standings, jersey leaders, status.
    """
    url = f"{PCS_BASE}/race/{race_slug}/{year}"
    html = await fetch_html(session, url)
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    data: dict[str, Any] = {
        "race_slug": race_slug,
        "year": year,
        "url": url,
    }

    # --- Race title ---
    title_el = soup.find("h1")
    data["race_name"] = _text(title_el)

    # --- Race dates ---
    date_el = soup.find("div", class_="date")
    if not date_el:
        date_el = soup.find("span", class_="date")
    data["race_dates"] = _text(date_el)

    # --- Stage list ---
    stages = _parse_stages(soup)
    data["stages"] = stages
    data["total_stages"] = len(stages)

    # --- Determine race status and current stage ---
    today = date.today()
    status, current_stage, next_stage = _determine_status(stages, today)
    data["status"] = status
    data["current_stage"] = current_stage
    data["next_stage"] = next_stage

    # --- GC standings ---
    gc = _parse_gc(soup)
    data["gc"] = gc
    data["gc_leader"] = gc[0] if gc else {}

    # --- Jersey leaders (points / mountain / youth) ---
    data["jerseys"] = _parse_jerseys(soup, race_slug)

    # --- Last completed stage winner ---
    last_stage = _last_completed_stage(stages)
    data["last_stage_winner"] = last_stage.get("winner", "") if last_stage else ""
    data["last_stage_number"] = last_stage.get("stage_number", "") if last_stage else ""
    data["last_stage_name"] = last_stage.get("name", "") if last_stage else ""

    return data


# ---------------------------------------------------------------------------
# Stage list
# ---------------------------------------------------------------------------

def _parse_stages(soup: BeautifulSoup) -> list[dict]:
    """Parse the stage list table from PCS race page."""
    stages = []
    table = soup.find("table", class_=re.compile(r"basic"))
    if not table:
        # Try alternate table structures
        table = soup.find("div", class_="mt10")
        if table:
            table = table.find("table")

    if not table:
        return stages

    rows = table.find_all("tr")
    for row in rows[1:]:  # skip header
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        stage: dict[str, Any] = {}

        # Stage number / type
        num_el = cols[0].find("a") or cols[0]
        stage_text = _text(num_el)
        stage["stage_number"] = stage_text

        # Date
        date_col = None
        for i, col in enumerate(cols):
            txt = _text(col)
            if re.match(r"\d{2}\.\d{2}", txt):
                date_col = txt
                break
        stage["date_str"] = date_col or ""
        stage["date"] = _parse_stage_date(date_col, None)

        # Stage name / route
        name_col = cols[-2] if len(cols) > 3 else cols[1]
        stage["name"] = _text(name_col)

        # Winner (if completed)
        winner_col = cols[-1]
        winner_link = winner_col.find("a")
        stage["winner"] = _text(winner_link) if winner_link else ""
        stage["completed"] = bool(stage["winner"])

        # Stage URL
        link = cols[0].find("a")
        if link and link.get("href"):
            stage["url"] = PCS_BASE + "/" + link["href"].lstrip("/")
        else:
            stage["url"] = ""

        stages.append(stage)

    return stages


def _parse_stage_date(date_str: str | None, year: int | None) -> date | None:
    """Parse DD.MM date string from PCS."""
    if not date_str:
        return None
    try:
        # PCS uses DD.MM format in the table
        m = re.match(r"(\d{1,2})\.(\d{1,2})", date_str)
        if m:
            day, month = int(m.group(1)), int(m.group(2))
            yr = year or date.today().year
            return date(yr, month, day)
    except (ValueError, AttributeError):
        pass
    return None


def _determine_status(stages: list[dict], today: date) -> tuple[str, dict, dict]:
    """Return (status, current_stage, next_stage)."""
    if not stages:
        return "unknown", {}, {}

    completed = [s for s in stages if s.get("completed")]
    upcoming = [s for s in stages if not s.get("completed")]

    if not completed and not upcoming:
        return "unknown", {}, {}

    if not completed:
        return "not_started", {}, upcoming[0] if upcoming else {}

    if not upcoming:
        return "finished", completed[-1], {}

    return "live", completed[-1], upcoming[0]


def _last_completed_stage(stages: list[dict]) -> dict | None:
    completed = [s for s in stages if s.get("completed")]
    return completed[-1] if completed else None


# ---------------------------------------------------------------------------
# GC standings
# ---------------------------------------------------------------------------

def _parse_gc(soup: BeautifulSoup) -> list[dict]:
    """Parse the General Classification standings table."""
    gc = []

    # PCS uses div.gcw or a specific table for GC
    gc_div = soup.find("div", id="general-classification")
    if not gc_div:
        # Try finding a table with 'gc' in class or preceding header
        for header in soup.find_all(["h3", "h4"]):
            if "general" in _text(header).lower() or "gc" in _text(header).lower():
                gc_div = header.find_next_sibling("div") or header.find_next_sibling("table")
                break

    if not gc_div:
        # Fallback: find first ranking-style table
        for table in soup.find_all("table"):
            headers = [_text(th) for th in table.find_all("th")]
            if any("time" in h.lower() or "gap" in h.lower() for h in headers):
                gc_div = table
                break

    if not gc_div:
        return gc

    table = gc_div if gc_div.name == "table" else gc_div.find("table")
    if not table:
        return gc

    rows = table.find_all("tr")
    for i, row in enumerate(rows[1:11]):  # top 10
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        rider: dict[str, Any] = {"rank": i + 1}

        # Find rider name (usually in an <a> tag)
        for col in cols:
            link = col.find("a")
            if link and link.get("href") and "rider" in link.get("href", ""):
                rider["name"] = _text(link)
                break
        if "name" not in rider:
            rider["name"] = _text(cols[1]) if len(cols) > 1 else ""

        # Time / gap — last column usually
        rider["time"] = _text(cols[-1])
        if not rider["time"] or rider["time"] == "0":
            rider["gap"] = "0:00"
        else:
            rider["gap"] = rider["time"]

        # Team — second to last, or look for team link
        for col in cols:
            link = col.find("a")
            if link and "team" in link.get("href", ""):
                rider["team"] = _text(link)
                break
        if "team" not in rider:
            rider["team"] = ""

        if rider.get("name"):
            gc.append(rider)

    return gc


# ---------------------------------------------------------------------------
# Jersey leaders
# ---------------------------------------------------------------------------

JERSEY_LABELS = {
    "points": ["points", "green", "cyclamen", "rojo"],
    "mountain": ["mountain", "polka", "maglia azzurra", "azul"],
    "youth": ["youth", "white", "white jersey", "bianca"],
}


def _parse_jerseys(soup: BeautifulSoup, race_slug: str) -> dict[str, str]:
    """Parse jersey leaders from the race page."""
    jerseys: dict[str, str] = {
        "points": "",
        "mountain": "",
        "youth": "",
    }

    # Look for jersey/classification sections
    for section in soup.find_all(["div", "ul"], class_=re.compile(r"leader|jersey|classif")):
        text = _text(section).lower()
        for jersey_type, keywords in JERSEY_LABELS.items():
            if any(kw in text for kw in keywords):
                link = section.find("a", href=re.compile(r"rider/"))
                if link:
                    jerseys[jersey_type] = _text(link)

    return jerseys


# ---------------------------------------------------------------------------
# Live stage data
# ---------------------------------------------------------------------------

async def get_live_stage_data(session: aiohttp.ClientSession, stage_url: str) -> dict[str, Any]:
    """
    Fetch a single stage page for live / result data.
    Returns winner, stage type, km, elevation.
    """
    if not stage_url:
        return {}

    html = await fetch_html(session, stage_url)
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    data: dict[str, Any] = {"url": stage_url}

    # Stage type (flat / mountain / ITT / TTT)
    profile_el = soup.find("div", class_=re.compile(r"profileIcon|stage-type"))
    data["stage_type"] = _text(profile_el) or _guess_stage_type(soup)

    # Distance
    for li in soup.find_all("li"):
        txt = _text(li).lower()
        m = re.search(r"(\d{2,3}(?:\.\d)?)\s*km", txt)
        if m:
            data["distance_km"] = m.group(1)
            break

    # Elevation
    for li in soup.find_all("li"):
        txt = _text(li)
        m = re.search(r"(\d{3,5})\s*m", txt)
        if m and int(m.group(1)) > 100:
            data["elevation_m"] = m.group(1)
            break

    # Winner (result table)
    result_table = soup.find("table", class_=re.compile(r"result|basic"))
    if result_table:
        rows = result_table.find_all("tr")
        for row in rows[1:2]:  # first result row = winner
            cols = row.find_all("td")
            for col in cols:
                link = col.find("a", href=re.compile(r"rider/"))
                if link:
                    data["winner"] = _text(link)
                    break

    # Start / finish cities
    route_el = soup.find("h2") or soup.find("div", class_="sub")
    if route_el:
        route_text = _text(route_el)
        if ">" in route_text or "–" in route_text or "-" in route_text:
            data["route"] = route_text

    return data


def _guess_stage_type(soup: BeautifulSoup) -> str:
    """Guess stage type from page text."""
    text = soup.get_text().lower()
    if "individual time" in text or "itt" in text:
        return "ITT"
    if "team time" in text or "ttt" in text:
        return "TTT"
    if "mountain" in text or "summit" in text:
        return "Mountain"
    return "Flat"
