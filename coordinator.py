"""DataUpdateCoordinator for Grand Cycling Tours."""

from __future__ import annotations

import logging
from datetime import timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, RACE_NAMES
from .pcs_scraper import get_race_data

_LOGGER = logging.getLogger(__name__)


class GrandTourCoordinator(DataUpdateCoordinator):
    """Coordinator that polls ProcyclingStats for all configured races."""

    def __init__(
        self,
        hass: HomeAssistant,
        races: list[str],
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval),
        )
        self.races = races
        self._session: aiohttp.ClientSession | None = None

    async def _async_update_data(self) -> dict:
        """Fetch data for all configured races."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        from datetime import date
        year = date.today().year

        results = {}
        errors = []

        for race_slug in self.races:
            try:
                _LOGGER.debug("Fetching data for %s %d", race_slug, year)
                data = await get_race_data(self._session, race_slug, year)
                if data:
                    results[race_slug] = data
                else:
                    _LOGGER.warning("No data returned for %s", race_slug)
                    results[race_slug] = self._empty_race(race_slug, year)
            except Exception as exc:  # pylint: disable=broad-except
                _LOGGER.error("Error fetching %s: %s", race_slug, exc)
                errors.append(str(exc))
                results[race_slug] = self._empty_race(race_slug, year)

        if errors and not results:
            raise UpdateFailed(f"All races failed: {'; '.join(errors)}")

        return results

    def _empty_race(self, race_slug: str, year: int) -> dict:
        return {
            "race_slug": race_slug,
            "race_name": RACE_NAMES.get(race_slug, race_slug),
            "year": year,
            "status": "unknown",
            "stages": [],
            "total_stages": 0,
            "current_stage": {},
            "next_stage": {},
            "gc": [],
            "gc_leader": {},
            "jerseys": {"points": "", "mountain": "", "youth": ""},
            "last_stage_winner": "",
            "last_stage_number": "",
            "last_stage_name": "",
        }

    async def async_close(self) -> None:
        """Close aiohttp session."""
        if self._session and not self._session.closed:
            await self._session.close()
