"""Sensor platform for Grand Cycling Tours."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    RACE_GIRO,
    RACE_TDF,
    RACE_VUELTA,
    RACE_NAMES,
)
from .coordinator import GrandTourCoordinator

_LOGGER = logging.getLogger(__name__)

# Fallback icon if no icon.png is present in the integration
FALLBACK_ICON = "mdi:bicycle"

# GC jersey emoji per race
RACE_GC_EMOJI = {
    RACE_TDF:   "🟡",
    RACE_GIRO:  "🩷",
    RACE_VUELTA: "🔴",
}

# Points jersey emoji per race
RACE_POINTS_EMOJI = {
    RACE_TDF:   "🟢",  # Green jersey
    RACE_GIRO:  "💜",  # Cyclamen (purple)
    RACE_VUELTA: "🟢",  # Green jersey
}

# Mountain jersey emoji per race
RACE_MOUNTAIN_EMOJI = {
    RACE_TDF:   "🔵",  # Polka dot
    RACE_GIRO:  "🔵",  # Blue jersey
    RACE_VUELTA: "🔵",  # Blue jersey
}

# Points jersey name per race
RACE_POINTS_NAME = {
    RACE_TDF:   "Points Jersey",
    RACE_GIRO:  "Cyclamen Jersey",
    RACE_VUELTA: "Points Jersey",
}

# Mountain jersey name per race
RACE_MOUNTAIN_NAME = {
    RACE_TDF:   "Mountains Jersey",
    RACE_GIRO:  "Mountains Jersey",
    RACE_VUELTA: "Mountains Jersey",
}

# GC jersey name per race
RACE_GC_NAME = {
    RACE_TDF:   "Yellow Jersey (GC)",
    RACE_GIRO:  "Pink Jersey (GC)",
    RACE_VUELTA: "Red Jersey (GC)",
}


def _sensor_types_for_race(race_slug: str) -> list[tuple[str, str, str]]:
    """Return sensor type definitions with race-specific labels."""
    gc_emoji = RACE_GC_EMOJI.get(race_slug, "🏆")
    pts_emoji = RACE_POINTS_EMOJI.get(race_slug, "🟢")
    mtn_emoji = RACE_MOUNTAIN_EMOJI.get(race_slug, "🔵")

    pts_name = RACE_POINTS_NAME.get(race_slug, "Points Jersey")
    mtn_name = RACE_MOUNTAIN_NAME.get(race_slug, "Mountains Jersey")
    gc_name = RACE_GC_NAME.get(race_slug, "GC Leader")

    return [
        ("status",          "Race Status",          "mdi:flag-checkered"),
        ("gc_leader",       gc_name,                "mdi:podium-gold"),
        ("stage_winner",    "Last Stage Winner",    "mdi:trophy"),
        ("next_stage",      "Next Stage",           "mdi:map-marker-path"),
        ("current_stage",   "Current Stage",        "mdi:map-marker"),
        ("points_leader",   pts_name,               "mdi:tshirt-crew"),
        ("mountain_leader", mtn_name,               "mdi:mountain"),
        ("youth_leader",    "White Jersey",         "mdi:account-school"),
        ("gc_top5",         "GC Top 5",             "mdi:format-list-numbered"),
        ("stage_count",     "Stages Completed",     "mdi:counter"),
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors from config entry."""
    coordinator: GrandTourCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities = []
    for race_slug in coordinator.races:
        for (sensor_key, sensor_name, icon) in _sensor_types_for_race(race_slug):
            entities.append(
                GrandTourSensor(
                    coordinator=coordinator,
                    race_slug=race_slug,
                    sensor_key=sensor_key,
                    sensor_name=sensor_name,
                    icon=icon,
                )
            )

    async_add_entities(entities, True)


class GrandTourSensor(CoordinatorEntity, SensorEntity):
    """A sensor for one aspect of one Grand Tour race."""

    def __init__(
        self,
        coordinator: GrandTourCoordinator,
        race_slug: str,
        sensor_key: str,
        sensor_name: str,
        icon: str,
    ) -> None:
        super().__init__(coordinator)
        self._race_slug = race_slug
        self._sensor_key = sensor_key

        race_name = RACE_NAMES.get(race_slug, race_slug)

        self._attr_name = f"{race_name} {sensor_name}"
        self._attr_unique_id = f"{DOMAIN}_{race_slug}_{sensor_key}"
        self._attr_icon = icon

        # Device info groups all sensors for one race
        self._attr_device_info = {
            "identifiers": {(DOMAIN, race_slug)},
            "name": race_name,
            "manufacturer": "ProcyclingStats",
            "model": "Grand Tour",
            "entry_type": "service",
        }

    @property
    def _race_data(self) -> dict:
        if self.coordinator.data is None:
            return {}
        return self.coordinator.data.get(self._race_slug, {})

    @property
    def native_value(self) -> str | int | None:
        d = self._race_data
        if not d:
            return None

        key = self._sensor_key

        if key == "status":
            status = d.get("status", "unknown")
            stage_num = (
                _stage_num(d.get("current_stage", {}))
                or _stage_num(d.get("next_stage", {}))
            )
            total = d.get("total_stages", "?")
            label = _status_label(status)
            return f"{label} (Stage {stage_num}/{total})" if stage_num else label

        if key == "gc_leader":
            gc = d.get("gc", [])
            return gc[0].get("name", "–") if gc else "–"

        if key == "stage_winner":
            winner = d.get("last_stage_winner", "")
            stage = d.get("last_stage_number", "")
            if winner:
                return f"Stage {stage}: {winner}" if stage else winner
            return "–"

        if key == "next_stage":
            ns = d.get("next_stage", {})
            if ns:
                parts = [
                    p for p in [
                        ns.get("stage_number", ""),
                        ns.get("name", ""),
                        ns.get("date_str", ""),
                    ] if p
                ]
                return " – ".join(parts) if parts else "No upcoming stage"
            return "No upcoming stage"

        if key == "current_stage":
            cs = d.get("current_stage", {})
            if cs:
                return cs.get("name", cs.get("stage_number", "–"))
            return "–"

        if key == "points_leader":
            return d.get("jerseys", {}).get("points", "") or "–"

        if key == "mountain_leader":
            return d.get("jerseys", {}).get("mountain", "") or "–"

        if key == "youth_leader":
            return d.get("jerseys", {}).get("youth", "") or "–"

        if key == "gc_top5":
            gc = d.get("gc", [])[:5]
            if not gc:
                return "–"
            lines = []
            for r in gc:
                gap = r.get("gap", "")
                gap_str = f" (+{gap})" if gap and gap not in ("0:00", "0") else ""
                lines.append(f"{r['rank']}. {r.get('name', '?')}{gap_str}")
            return " | ".join(lines)

        if key == "stage_count":
            completed = sum(1 for s in d.get("stages", []) if s.get("completed"))
            total = d.get("total_stages", 0)
            return f"{completed}/{total}"

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        d = self._race_data
        if not d:
            return {}

        key = self._sensor_key
        attrs: dict[str, Any] = {
            "race": RACE_NAMES.get(self._race_slug, self._race_slug),
            "year": d.get("year"),
            "race_url": d.get("url", ""),
        }

        if key in ("gc_leader", "gc_top5"):
            gc = d.get("gc", [])
            attrs["gc_standings"] = gc
            if gc:
                leader = gc[0]
                attrs["leader_name"] = leader.get("name", "")
                attrs["leader_team"] = leader.get("team", "")
                attrs["leader_gap"] = leader.get("gap", "")

        if key == "status":
            attrs["race_dates"] = d.get("race_dates", "")
            attrs["total_stages"] = d.get("total_stages", 0)
            attrs["stages_completed"] = sum(
                1 for s in d.get("stages", []) if s.get("completed")
            )

        if key == "next_stage":
            ns = d.get("next_stage", {})
            attrs.update({
                "stage_number": ns.get("stage_number", ""),
                "stage_name": ns.get("name", ""),
                "stage_date": ns.get("date_str", ""),
                "stage_url": ns.get("url", ""),
            })

        if key == "stage_winner":
            attrs["stage_number"] = d.get("last_stage_number", "")
            attrs["stage_name"] = d.get("last_stage_name", "")
            attrs["winner"] = d.get("last_stage_winner", "")

        if key == "gc_top5":
            for i, rider in enumerate(d.get("gc", [])[:5], 1):
                attrs[f"pos_{i}_name"] = rider.get("name", "")
                attrs[f"pos_{i}_team"] = rider.get("team", "")
                attrs[f"pos_{i}_gap"] = rider.get("gap", "")

        return attrs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _status_label(status: str) -> str:
    return {
        "not_started": "Not started",
        "live":        "Live",
        "finished":    "Finished",
        "unknown":     "Unknown",
    }.get(status, status)


def _stage_num(stage_dict: dict) -> str:
    if not stage_dict:
        return ""
    num = stage_dict.get("stage_number", "")
    m = re.search(r"\d+", str(num))
    return m.group() if m else ""
