"""
Scraper for ProcyclingStats.com — fetches Grand Tour data.

Data is scraped from public HTML pages (no API key required).
Scraped fields:
  - Race status (not started / live / finished) — date-based
  - Current / next stage info
  - GC top 10
  - Stage winner
  - Points / KOM / Youth jersey leaders (race-specific, section-isolated)
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

import aiohttp
from bs4 import BeautifulSoup, Tag

_LOGGER = logging.getLogger(__name__)

PCS_BASE = "https://www.procyclingstats.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; HomeAssistant/GrandCyclingTours/1.0)"
}

RACE_JERSEY_HEADINGS = {
    "tour-de-france": {
        "points":   ["points classification", "green jersey"],
        "mountain": ["mountain classification", "king of the mountains", "polka dot"],
        "youth":    ["young rider classification", "white jersey"],
    },
    "giro-d-italia": {
        "points":   ["points classification", "maglia ciclamino", "cyclamen"],
        "mountain": ["mountain classification", "maglia azzurra"],
        "youth":    ["young rider classification", "maglia bianca", "white jersey"],
    },
    "vuelta-a-espana": {
        "points":   ["points classification", "maillot verde", "green jersey"],
        "mountain": ["mountain classification", "maillot de lunares"],
        "youth":    ["young rider classification", "maillot blanco", "white jersey"],
    },
}


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

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
# Main entry point
# ---------------------------------------------------------------------------

async def get_race_data(
    session: aiohttp.ClientSession, race_slug: str, year: int
) -> dict[str, Any]:
    """
    Fetch race data from two PCS pages:
    1. /race/<slug>/statistics — for reliable status & next race date
    2. /race/<slug>/<year> — for stages, GC, jerseys, winners
    """
    # --- Fetch statistics page for authoritative status info ---
    stats_url = f"{PCS_BASE}/race/{race_slug}/statistics"
    stats_html = await fetch_html(session, stats_url)
    stats_info = _parse_statistics_page(stats_html, year) if stats_html else {}

    # --- Fetch the year-specific race page ---
    url = f"{PCS_BASE}/race/{race_slug}/{year}"
    html = await fetch_html(session, url)
    if not html:
        return {}

    soup = BeautifulSoup(html, "html.parser")
    data: dict[str, Any] = {"race_slug": race_slug, "year": year, "url": url}

    # Race title
    title_el = soup.find("h1")
    data["race_name"] = _text(title_el)

    # Race dates string from race page
    date_el = soup.find("div", class_="date") or soup.find("span", class_="date")
    data["race_dates"] = _text(date_el)

    # Stage list
    stages = _parse_stages(soup)
    data["stages"] = stages
    data["total_stages"] = len(stages)

    # --- Determine race dates: prefer statistics page, fall back to stages ---
    race_start = stats_info.get("next_race_date")  # only set if upcoming
    race_end = None

    if not race_start:
        # Race is in the past or currently running — derive from stages
        race_start, race_end = _dates_from_stages(stages)

    if not race_start:
        # Last fallback: scrape header string
        race_start, race_end = _parse_race_dates(soup, data["race_dates"])

    # If we have start but no end, derive end from stage list
    if race_start and not race_end:
        _, race_end = _dates_from_stages(stages)

    data["race_start"] = race_start.isoformat() if race_start else ""
    data["race_end"] = race_end.isoformat() if race_end else ""

    # --- Status: statistics page is authoritative ---
    today = date.today()
    status = _determine_status_from_stats(stats_info, year, today, race_start, race_end)

    # Set current/next stage based on resolved status
    if status == "not_started":
        current_stage = {}
        next_stage = stages[0] if stages else {}
    elif status == "finished":
        current_stage = stages[-1] if stages else {}
        next_stage = {}
    elif status == "live":
        completed = [s for s in stages if s.get("completed")]
        upcoming = [s for s in stages if not s.get("completed")]
        current_stage = completed[-1] if completed else {}
        next_stage = upcoming[0] if upcoming else {}
    else:
        current_stage, next_stage = {}, {}

    data["status"] = status
    data["current_stage"] = current_stage
    data["next_stage"] = next_stage
    data["days_until_start"] = stats_info.get("days_until_start", "")
    data["last_year_winner"] = stats_info.get("last_year_winner", "")

    # --- GC standings — show for live and finished races ---
    if status in ("live", "finished"):
        gc = _parse_gc(soup)
    else:
        gc = []
    data["gc"] = gc
    data["gc_leader"] = gc[0] if gc else {}

    # --- Jersey leaders — show for live and finished races ---
    if status in ("live", "finished"):
        data["jerseys"] = _parse_jerseys(soup, race_slug)
    else:
        data["jerseys"] = {"points": "", "mountain": "", "youth": ""}

    # --- Last completed stage winner ---
    last_stage = _last_completed_stage(stages)
    if last_stage:
        winner = last_stage.get("winner", "")
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
# Statistics page parsing — authoritative source for race status
# ---------------------------------------------------------------------------

def _parse_statistics_page(html: str, year: int) -> dict[str, Any]:
    """
    Parse the /race/<slug>/statistics page.
    Returns:
      - days_until_start: int or None (set when race is upcoming)
      - next_race_date: date or None (precise start date when race is upcoming)
      - last_winners: dict {year: winner_name}
      - current_year_winner: name if this year already has a recorded winner
      - last_year_winner: previous year's winner
    """
    result: dict[str, Any] = {
        "days_until_start": None,
        "next_race_date": None,
        "last_winners": {},
        "current_year_winner": "",
        "last_year_winner": "",
    }

    soup = BeautifulSoup(html, "html.parser")
    page_text = soup.get_text(" ", strip=True)

    # --- "It is X days untill the start of [race] at Month Dth YYYY." ---
    m = re.search(
        r"(\d+)\s+days?\s+untill?\s+the\s+start\s+of[^.]*?at\s+"
        r"([A-Za-z]+)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})",
        page_text,
        re.IGNORECASE,
    )
    if m:
        try:
            result["days_until_start"] = int(m.group(1))
            month_name = m.group(2)
            day = int(m.group(3))
            yr = int(m.group(4))
            month = _month_name_to_num(month_name)
            if month:
                result["next_race_date"] = date(yr, month, day)
        except ValueError:
            pass

    # --- "Last winners" section: parse year → winner pairs ---
    # Look for the heading and then walk the following content
    for header in soup.find_all(["h3", "h4", "b", "strong"]):
        if "last winners" in _text(header).lower():
            container = header.find_parent(["div", "td"]) or header.parent
            if container:
                # Find all year links and their associated winner text
                text = container.get_text("\n", strip=True)
                for line_match in re.finditer(
                    r"(\d{4})\s+([A-ZÀ-Ý][A-ZÀ-Ýa-zà-ÿ'\-\s]+?)(?=\s*\d{4}|\s*$)",
                    text,
                ):
                    try:
                        winner_year = int(line_match.group(1))
                        winner_name = line_match.group(2).strip()
                        # Filter out very short or empty names
                        if winner_name and len(winner_name) > 2:
                            result["last_winners"][winner_year] = winner_name
                    except ValueError:
                        continue
            break

    result["current_year_winner"] = result["last_winners"].get(year, "")
    result["last_year_winner"] = result["last_winners"].get(year - 1, "")

    return result


def _month_name_to_num(name: str) -> int | None:
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    return months.get(name.lower())


def _determine_status_from_stats(
    stats_info: dict,
    year: int,
    today: date,
    race_start: date | None,
    race_end: date | None,
) -> str:
    """
    Determine race status using statistics page info first.
    Falls back to date-based logic.
    """
    # 1. Statistics page explicitly says race is upcoming
    days_until = stats_info.get("days_until_start")
    if days_until is not None and days_until > 0:
        return "not_started"

    # 2. Statistics page shows a winner for this year → finished
    if stats_info.get("current_year_winner"):
        return "finished"

    # 3. Date-based fallback
    if race_start and race_end:
        if today < race_start:
            return "not_started"
        if today > race_end:
            return "finished"
        return "live"

    # 4. If we know the start date but no end — derive
    if race_start:
        if today < race_start:
            return "not_started"
        # Assume Grand Tour is 3 weeks long
        from datetime import timedelta
        if today > race_start + timedelta(days=24):
            return "finished"
        return "live"

    return "unknown"


# ---------------------------------------------------------------------------
# Race date resolution — derived from stage list (no hardcoding)
# ---------------------------------------------------------------------------

def _dates_from_stages(stages: list[dict]) -> tuple[date | None, date | None]:
    """
    Derive race start and end dates from the stage list.
    Uses the date of the first and last stage — works for any year automatically.
    """
    dated = [s for s in stages if s.get("date")]
    if not dated:
        return None, None
    return dated[0]["date"], dated[-1]["date"]


def _parse_race_dates(soup: BeautifulSoup, dates_str: str) -> tuple[date | None, date | None]:
    """
    Fallback: parse race dates from the PCS page header string.
    PCS typically shows e.g. '08.05 – 01.06 2026'.
    """
    year = date.today().year

    m = re.search(
        r"(\d{1,2})\.(\d{2})\s*[-–]\s*(\d{1,2})\.(\d{2})(?:\s+(\d{4}))?",
        dates_str
    )
    if m:
        try:
            yr = int(m.group(5)) if m.group(5) else year
            start = date(yr, int(m.group(2)), int(m.group(1)))
            end = date(yr, int(m.group(4)), int(m.group(3)))
            return start, end
        except ValueError:
            pass

    for el in soup.find_all(["span", "div"], class_=re.compile(r"date|period", re.I)):
        txt = _text(el)
        m = re.search(r"(\d{1,2})\.(\d{2})\s*[-–]\s*(\d{1,2})\.(\d{2})", txt)
        if m:
            try:
                start = date(year, int(m.group(2)), int(m.group(1)))
                end = date(year, int(m.group(4)), int(m.group(3)))
                return start, end
            except ValueError:
                pass

    return None, None



# ---------------------------------------------------------------------------
# Status determination — date-based
# ---------------------------------------------------------------------------

def _determine_status(
    stages: list[dict],
    today: date,
    race_start: date | None,
    race_end: date | None,
) -> tuple[str, dict, dict]:
    """
    Determine race status using dates first, then fall back to winner detection.
    Returns (status, current_or_last_stage, next_stage).
    """
    # --- Date-based determination (most reliable) ---
    if race_start and race_end:
        if today < race_start:
            # Not started — next stage is the first stage
            first = stages[0] if stages else {}
            return "not_started", {}, first
        if today > race_end:
            # Finished — show last stage
            last = stages[-1] if stages else {}
            return "finished", last, {}
        # Race is live — find today's or most recent stage
        return _live_status_from_stages(stages, today)

    # --- Fallback: winner-based detection ---
    completed = [s for s in stages if s.get("completed")]
    upcoming = [s for s in stages if not s.get("completed")]

    if not stages:
        return "unknown", {}, {}
    if not completed:
        return "not_started", {}, stages[0]
    if not upcoming:
        return "finished", completed[-1], {}
    return "live", completed[-1], upcoming[0]


def _live_status_from_stages(
    stages: list[dict], today: date
) -> tuple[str, dict, dict]:
    """Find current and next stage during a live race."""
    completed = [s for s in stages if s.get("completed")]
    upcoming = [s for s in stages if not s.get("completed")]

    current = completed[-1] if completed else {}
    nxt = upcoming[0] if upcoming else {}
    return "live", current, nxt


def _last_completed_stage(stages: list[dict]) -> dict | None:
    completed = [s for s in stages if s.get("completed")]
    return completed[-1] if completed else None


# ---------------------------------------------------------------------------
# Stage list parsing
# ---------------------------------------------------------------------------

def _parse_stages(soup: BeautifulSoup) -> list[dict]:
    """Parse the stage list table from PCS race page."""
    stages = []
    table = soup.find("table", class_=re.compile(r"basic")) or _find_stage_table(soup)
    if not table:
        return stages

    for row in table.find_all("tr")[1:]:  # skip header
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        stage: dict[str, Any] = {}

        # Stage number
        num_el = cols[0].find("a") or cols[0]
        stage["stage_number"] = _text(num_el)

        # Date
        date_col = next(
            (_text(c) for c in cols if re.match(r"\d{1,2}\.\d{2}", _text(c))), ""
        )
        stage["date_str"] = date_col
        stage["date"] = _parse_stage_date(date_col)

        # Stage name
        name_col = cols[-2] if len(cols) > 3 else cols[1]
        stage["name"] = _text(name_col)

        # Winner
        winner_col = cols[-1]
        winner_link = winner_col.find("a", href=re.compile(r"rider/")) or winner_col.find("a")
        stage["winner"] = _text(winner_link) if winner_link else ""
        stage["completed"] = bool(stage["winner"])

        # Stage URL
        link = cols[0].find("a")
        stage["url"] = (
            PCS_BASE + "/" + link["href"].lstrip("/")
            if link and link.get("href") else ""
        )

        stages.append(stage)

    return stages


def _find_stage_table(soup: BeautifulSoup) -> Tag | None:
    for cls in ["mt10", "mt20", "race-info", "content"]:
        div = soup.find("div", class_=cls)
        if div:
            tbl = div.find("table")
            if tbl:
                return tbl
    for table in soup.find_all("table"):
        headers = [_text(th).lower() for th in table.find_all("th")]
        if any(h in headers for h in ["stage", "date", "winner", "distance"]):
            return table
    return None


def _parse_stage_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        m = re.match(r"(\d{1,2})\.(\d{1,2})", date_str)
        if m:
            return date(date.today().year, int(m.group(2)), int(m.group(1)))
    except ValueError:
        pass
    return None


# ---------------------------------------------------------------------------
# GC standings
# ---------------------------------------------------------------------------

def _parse_gc(soup: BeautifulSoup) -> list[dict]:
    """Parse GC top 10."""
    gc = []
    table = _find_gc_table(soup)
    if not table:
        return gc

    for i, row in enumerate(table.find_all("tr")[1:11]):
        cols = row.find_all("td")
        if len(cols) < 3:
            continue

        rider: dict[str, Any] = {"rank": i + 1}

        for col in cols:
            link = col.find("a", href=re.compile(r"rider/"))
            if link:
                rider["name"] = _text(link)
                break
        if "name" not in rider:
            rider["name"] = _text(cols[1]) if len(cols) > 1 else ""

        for col in cols:
            link = col.find("a", href=re.compile(r"team/"))
            if link:
                rider["team"] = _text(link)
                break
        if "team" not in rider:
            rider["team"] = ""

        rider["gap"] = _text(cols[-1]) or "0:00"

        if rider.get("name"):
            gc.append(rider)

    return gc


def _find_gc_table(soup: BeautifulSoup) -> Tag | None:
    # Strategy 1: explicit id
    div = soup.find("div", id="general-classification")
    if div:
        tbl = div.find("table")
        if tbl:
            return tbl

    # Strategy 2: heading + sibling
    for tag in ["h3", "h4", "h2"]:
        for header in soup.find_all(tag):
            if "general classification" in _text(header).lower():
                sib = header.find_next_sibling(["table", "div"])
                if sib:
                    return sib if sib.name == "table" else sib.find("table")

    # Strategy 3: table with time/gap headers
    for table in soup.find_all("table"):
        headers = [_text(th).lower() for th in table.find_all("th")]
        if any(h in headers for h in ["time", "gap", "+"]):
            return table

    # Strategy 4: div class
    for div in soup.find_all("div", class_=re.compile(r"\bgc\b|general", re.I)):
        tbl = div.find("table")
        if tbl:
            return tbl

    return None


# ---------------------------------------------------------------------------
# Jersey leaders — isolated per section to avoid cross-contamination
# ---------------------------------------------------------------------------

def _parse_jerseys(soup: BeautifulSoup, race_slug: str) -> dict[str, str]:
    """
    Parse jersey leaders by finding the dedicated classification section
    for each jersey type and extracting only the leader from that section.
    This prevents the same rider appearing in all jerseys.
    """
    jerseys: dict[str, str] = {"points": "", "mountain": "", "youth": ""}
    headings = RACE_JERSEY_HEADINGS.get(race_slug, {})

    for jersey_type, kw_list in headings.items():
        leader = _find_jersey_leader_in_section(soup, kw_list)
        if leader:
            jerseys[jersey_type] = leader

    return jerseys


def _find_jersey_leader_in_section(
    soup: BeautifulSoup, heading_keywords: list[str]
) -> str:
    """
    Find the leader of a specific classification by:
    1. Locating the section heading that matches one of the keywords
    2. Looking for the first rider link within that specific section only
    3. NOT scanning the whole page (avoids cross-contamination)
    """
    for tag in ["h3", "h4", "h2", "h5"]:
        for header in soup.find_all(tag):
            header_text = _text(header).lower()
            if not any(kw in header_text for kw in heading_keywords):
                continue

            # Found a matching heading — search the next sibling block only
            sibling = header.find_next_sibling(["div", "ul", "table", "ol"])
            if not sibling:
                continue

            # Get the first rider link in this section
            link = sibling.find("a", href=re.compile(r"rider/"))
            if link:
                return _text(link)

            # Sometimes the rider is in the first table row
            row = sibling.find("tr")
            if row:
                link = row.find("a", href=re.compile(r"rider/"))
                if link:
                    return _text(link)

    # Fallback: look for dedicated classification divs by id or class
    for kw in heading_keywords:
        slug = kw.replace(" ", "-")
        div = (
            soup.find("div", id=re.compile(slug, re.I))
            or soup.find("div", class_=re.compile(slug, re.I))
        )
        if div:
            link = div.find("a", href=re.compile(r"rider/"))
            if link:
                return _text(link)

    return ""


# ---------------------------------------------------------------------------
# Individual stage page
# ---------------------------------------------------------------------------

async def get_live_stage_data(
    session: aiohttp.ClientSession, stage_url: str
) -> dict[str, Any]:
    """Fetch a single stage page for result data."""
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

    # Winner — first result row
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
