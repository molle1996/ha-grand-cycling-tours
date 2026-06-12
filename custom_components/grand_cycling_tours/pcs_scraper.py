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
from datetime import date
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

# Per-race jersey classification keywords on PCS
RACE_JERSEY_KEYS = {
    "tour-de-france": {
        "points":   ["points classification", "green jersey", "points"],
        "mountain": ["mountain classification", "polka dot", "king of the mountains", "mountain"],
        "youth":    ["young rider", "white jersey", "youth classification"],
    },
    "giro-d-italia": {
        "points":   ["points classification", "maglia ciclamino", "cyclamen jersey", "points"],
        "mountain": ["mountain classification", "maglia azzurra", "mountains", "mountain"],
        "youth":    ["young rider", "maglia bianca", "white jersey", "youth"],
    },
    "vuelta-a-espana": {
        "points":   ["points classification", "green jersey", "maillot verde", "points"],
        "mountain": ["mountain classification", "maillot de lunares", "mountains", "mountain"],
        "youth":    ["young rider", "maillot blanco", "white jersey", "youth"],
    },
}

# Fallback generic keywords
GENERIC_JERSEY_KEYS = {
    "points":   ["points", "green", "cyclamen", "rojo", "verde"],
    "mountain": ["mountain", "polka", "azzurra", "lunares", "kom"],
    "youth":    ["youth", "white", "young", "bianca", "blanco"],
}


async def fetch_html(session: aiohttp.ClientSession, url: str) -> str | None:
    """Fetch raw HTML from a URL."""
    try:
        async with session.get(
            url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=20)
        ) as resp:
            if resp.status == 200:
                return await resp.text()
            _LOGGER.warning("HTTP %s for %s", resp.status, url)
    except Exception as exc:  # pylint: disable=broad-except
        _LOGGER.error("Fetch error for %s: %s", url, exc)
    return None


def _text(el) -> str:
    return el.get_text(strip=True) if el else ""


# ---------------------------------------------------------------------------
# Race overview page
# ---------------------------------------------------------------------------

async def get_race_data(
    session: aiohttp.ClientSession, race_slug: str, year: int
) -> dict[str, Any]:
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
    date_el = soup.find("div", class_="date") or soup.find("span", class_="date")
    data["race_dates"] = _text(date_el)

    # --- Stage list ---
    stages = _parse_stages(soup)
    data["stages"] = stages
    data["total_stages"] = len(stages)

    # --- Determine race status ---
    today = date.today()
    status, current_stage, next_stage = _determine_status(stages, today)
    data["status"] = status
    data["current_stage"] = current_stage
    data["next_stage"] = next_stage

    # --- GC standings ---
    gc = _parse_gc(soup)
    data["gc"] = gc
    data["gc_leader"] = gc[0] if gc else {}

    # --- Jersey leaders ---
    data["jerseys"] = _parse_jerseys(soup, race_slug)

    # --- Last completed stage winner ---
    # First try from stage list, then fall back to fetching the stage page
    last_stage = _last_completed_stage(stages)
    if last_stage:
        winner = last_stage.get("winner", "")
        # If stage list didn't capture winner, try fetching the stage page
        if not winner and last_stage.get("url"):
            stage_data = await get_live_stage_data(session, last_stage["url"])
            winner = stage_data.get("winner", "")
        data["last_stage_winner"] = winner
        data["last_stage_number"] = last_stage.get("stage_number", "")
        data["last_stage_name"] = last_stage.get("name", "")
    else:
        data["last_stage_winner"] = ""
        data["last_stage_number"] = ""
        data["last_stage_name"] = ""

    return data


# ---------------------------------------------------------------------------
# Stage list parsing
# ---------------------------------------------------------------------------

def _parse_stages(soup: BeautifulSoup) -> list[dict]:
    """Parse the stage list table from PCS race page."""
    stages = []

    # PCS wraps stage tables in various ways — try multiple selectors
    table = (
        soup.find("table", class_=re.compile(r"basic"))
        or _find_stage_table(soup)
    )
    if not table:
        return stages

    rows = table.find_all("tr")
    for row in rows[1:]:  # skip header row
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        stage: dict[str, Any] = {}

        # Stage number — first column
        num_el = cols[0].find("a") or cols[0]
        stage["stage_number"] = _text(num_el)

        # Date — find column matching DD.MM pattern
        date_col = next(
            (_text(c) for c in cols if re.match(r"\d{1,2}\.\d{2}", _text(c))),
            ""
        )
        stage["date_str"] = date_col
        stage["date"] = _parse_stage_date(date_col)

        # Stage name / route — second-to-last column
        name_col = cols[-2] if len(cols) > 3 else cols[1]
        stage["name"] = _text(name_col)

        # Winner — last column, look for rider link first
        winner_col = cols[-1]
        winner_link = winner_col.find("a", href=re.compile(r"rider/"))
        if not winner_link:
            winner_link = winner_col.find("a")
        stage["winner"] = _text(winner_link) if winner_link else ""
        stage["completed"] = bool(stage["winner"])

        # Stage URL
        link = cols[0].find("a")
        stage["url"] = (
            PCS_BASE + "/" + link["href"].lstrip("/")
            if link and link.get("href")
            else ""
        )

        stages.append(stage)

    return stages


def _find_stage_table(soup: BeautifulSoup):
    """Try to find the stage table by alternate means."""
    # Look inside common wrapper divs
    for wrapper_class in ["mt10", "mt20", "race-info", "content"]:
        div = soup.find("div", class_=wrapper_class)
        if div:
            tbl = div.find("table")
            if tbl:
                return tbl

    # Last resort: any table with stage-like headers
    for table in soup.find_all("table"):
        headers = [_text(th).lower() for th in table.find_all("th")]
        if any(h in headers for h in ["stage", "date", "winner", "distance"]):
            return table

    return None


def _parse_stage_date(date_str: str | None) -> date | None:
    """Parse DD.MM date string from PCS."""
    if not date_str:
        return None
    try:
        m = re.match(r"(\d{1,2})\.(\d{1,2})", date_str)
        if m:
            day, month = int(m.group(1)), int(m.group(2))
            return date(date.today().year, month, day)
    except (ValueError, AttributeError):
        pass
    return None


def _determine_status(
    stages: list[dict], today: date
) -> tuple[str, dict, dict]:
    """Return (status, last_completed_stage, next_stage)."""
    if not stages:
        return "unknown", {}, {}

    completed = [s for s in stages if s.get("completed")]
    upcoming = [s for s in stages if not s.get("completed")]

    if not completed and not upcoming:
        return "unknown", {}, {}
    if not completed:
        return "not_started", {}, upcoming[0]
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

    table = _find_gc_table(soup)
    if not table:
        return gc

    rows = table.find_all("tr")
    for i, row in enumerate(rows[1:11]):  # top 10
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        rider: dict[str, Any] = {"rank": i + 1}

        # Rider name — prefer link with /rider/ in href
        for col in cols:
            link = col.find("a", href=re.compile(r"rider/"))
            if link:
                rider["name"] = _text(link)
                break
        if "name" not in rider:
            rider["name"] = _text(cols[1]) if len(cols) > 1 else ""

        # Team — prefer link with /team/ in href
        for col in cols:
            link = col.find("a", href=re.compile(r"team/"))
            if link:
                rider["team"] = _text(link)
                break
        if "team" not in rider:
            rider["team"] = ""

        # Time gap — last column
        rider["gap"] = _text(cols[-1]) or "0:00"

        if rider.get("name"):
            gc.append(rider)

    return gc


def _find_gc_table(soup: BeautifulSoup):
    """Find the GC table using multiple strategies."""
    # Strategy 1: explicit id
    div = soup.find("div", id="general-classification")
    if div:
        tbl = div.find("table")
        if tbl:
            return tbl

    # Strategy 2: heading followed by table
    for tag in ["h3", "h4", "h2"]:
        for header in soup.find_all(tag):
            txt = _text(header).lower()
            if "general classification" in txt or "overall" in txt:
                sibling = header.find_next_sibling(["table", "div"])
                if sibling:
                    return sibling if sibling.name == "table" else sibling.find("table")

    # Strategy 3: table with time/gap columns
    for table in soup.find_all("table"):
        headers = [_text(th).lower() for th in table.find_all("th")]
        if any(h in headers for h in ["time", "gap", "+"]):
            return table

    # Strategy 4: div with class containing 'gc' or 'general'
    for div in soup.find_all("div", class_=re.compile(r"gc|general", re.I)):
        tbl = div.find("table")
        if tbl:
            return tbl

    return None


# ---------------------------------------------------------------------------
# Jersey leaders
# ---------------------------------------------------------------------------

def _parse_jerseys(soup: BeautifulSoup, race_slug: str) -> dict[str, str]:
    """
    Parse jersey leaders. Uses race-specific keywords first,
    then falls back to generic keywords.
    """
    jerseys: dict[str, str] = {"points": "", "mountain": "", "youth": ""}
    keys = RACE_JERSEY_KEYS.get(race_slug, GENERIC_JERSEY_KEYS)

    # Strategy 1: dedicated classification divs/sections
    for section in soup.find_all(
        ["div", "li", "tr"], class_=re.compile(r"leader|jersey|classif|ranking", re.I)
    ):
        _match_jersey(section, jerseys, keys)

    # Strategy 2: scan all headings and their following sibling content
    if not all(jerseys.values()):
        for tag in ["h3", "h4", "h2", "h5"]:
            for header in soup.find_all(tag):
                header_text = _text(header).lower()
                for jersey_type, kw_list in keys.items():
                    if jerseys[jersey_type]:
                        continue
                    if any(kw in header_text for kw in kw_list):
                        # Look for a rider link near this heading
                        sibling = header.find_next_sibling(["div", "ul", "table", "p"])
                        if sibling:
                            link = sibling.find("a", href=re.compile(r"rider/"))
                            if link:
                                jerseys[jersey_type] = _text(link)

    # Strategy 3: scan entire page text for classification blocks
    if not all(jerseys.values()):
        for div in soup.find_all("div"):
            _match_jersey(div, jerseys, keys)

    return jerseys


def _match_jersey(
    element, jerseys: dict[str, str], keys: dict[str, list[str]]
) -> None:
    """Try to match a jersey leader from an HTML element."""
    text = _text(element).lower()
    for jersey_type, kw_list in keys.items():
        if jerseys[jersey_type]:
            continue
        if any(kw in text for kw in kw_list):
            link = element.find("a", href=re.compile(r"rider/"))
            if link:
                jerseys[jersey_type] = _text(link)


# ---------------------------------------------------------------------------
# Individual stage page
# ---------------------------------------------------------------------------

async def get_live_stage_data(
    session: aiohttp.ClientSession, stage_url: str
) -> dict[str, Any]:
    """
    Fetch a single stage page for live / result data.
    Returns winner, stage type, distance, elevation.
    """
    if not stage_url:
        return {}

    html = await fetch_html(session, stage_url)
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    data: dict[str, Any] = {"url": stage_url}

    # Stage type
    profile_el = soup.find("div", class_=re.compile(r"profileIcon|stage-type", re.I))
    data["stage_type"] = _text(profile_el) or _guess_stage_type(soup)

    # Distance
    for li in soup.find_all("li"):
        m = re.search(r"(\d{2,3}(?:\.\d)?)\s*km", _text(li).lower())
        if m:
            data["distance_km"] = m.group(1)
            break

    # Elevation
    for li in soup.find_all("li"):
        m = re.search(r"(\d{3,5})\s*m", _text(li))
        if m and int(m.group(1)) > 100:
            data["elevation_m"] = m.group(1)
            break

    # Winner — first row of result table
    result_table = soup.find("table", class_=re.compile(r"result|basic"))
    if result_table:
        for row in result_table.find_all("tr")[1:2]:
            for col in row.find_all("td"):
                link = col.find("a", href=re.compile(r"rider/"))
                if link:
                    data["winner"] = _text(link)
                    break

    # Route
    for el in [soup.find("h2"), soup.find("div", class_="sub")]:
        if el:
            txt = _text(el)
            if any(sep in txt for sep in [">", "–", "-"]):
                data["route"] = txt
                break

    return data


def _guess_stage_type(soup: BeautifulSoup) -> str:
    text = soup.get_text().lower()
    if "individual time" in text or " itt" in text:
        return "ITT"
    if "team time" in text or " ttt" in text:
        return "TTT"
    if "mountain" in text or "summit finish" in text:
        return "Mountain"
    return "Flat"
