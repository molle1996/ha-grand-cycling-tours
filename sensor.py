"""Sensor platform for Grand Cycling Tours."""

from __future__ import annotations

import logging
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

# Emoji / badge prefix per race
RACE_BADGE = {
    RACE_TDF: "🟡",   # yellow jersey
    RACE_GIRO: "🩷",   # pink jersey
    RACE_VUELTA: "🔴",  # red jersey
}

# Sensor definitions: (key, name_suffix, icon, attribute_key)
SENSOR_TYPES = [
    # name suffix, unique suffix, icon, value_fn, attr_fn
    ("status", "Race Status", "mdi:flag-checkered"),
    ("gc_leader", "GC Leader", "mdi:podium-gold"),
    ("stage_winner", "Last Stage Winner", "mdi:trophy"),
    ("next_stage", "Next Stage", "mdi:map-marker-path"),
    ("current_stage", "Current Stage", "mdi:map-marker"),
    ("points_leader", "Points Jersey Leader", "mdi:tshirt-crew"),
    ("mountain_leader", "Mountain Jersey Leader", "mdi:mountain"),
    ("youth_leader", "Youth Jersey Leader", "mdi:account-school"),
    ("gc_top5", "GC Top 5", "mdi:format-list-numbered"),
    ("stage_count", "Stages Completed", "mdi:counter"),
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
        for (sensor_key, sensor_name, icon) in SENSOR_TYPES:
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
        self._icon = icon

        race_name = RACE_NAMES.get(race_slug, race_slug)
        race_short = _race_short(race_slug)

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
            stage_num = _stage_num(d.get("current_stage", {})) or _stage_num(d.get("next_stage", {}))
            total = d.get("total_stages", "?")
            label = _status_label(status)
            if stage_num:
                return f"{label} (Stage {stage_num}/{total})"
            return label

        if key == "gc_leader":
            gc = d.get("gc", [])
            if gc:
                leader = gc[0]
                return leader.get("name", "")
            return "–"

        if key == "stage_winner":
            winner = d.get("last_stage_winner", "")
            stage = d.get("last_stage_number", "")
            if winner:
                return f"E{stage}: {winner}" if stage else winner
            return "–"

        if key == "next_stage":
            ns = d.get("next_stage", {})
            if ns:
                name = ns.get("name", "")
                date_str = ns.get("date_str", "")
                num = ns.get("stage_number", "")
                parts = [p for p in [num, name, date_str] if p]
                return " – ".join(parts) if parts else "No upcoming stage"
            return "No upcoming stage"

        if key == "current_stage":
            cs = d.get("current_stage", {})
            if cs:
                return cs.get("name", cs.get("stage_number", "–"))
            return "–"

        if key == "points_leader":
            return d.get("jerseys", {}).get("points", "–") or "–"

        if key == "mountain_leader":
            return d.get("jerseys", {}).get("mountain", "–") or "–"

        if key == "youth_leader":
            return d.get("jerseys", {}).get("youth", "–") or "–"

        if key == "gc_top5":
            gc = d.get("gc", [])[:5]
            if not gc:
                return "–"
            lines = []
            for r in gc:
                gap = r.get("gap", "")
                gap_str = f" (+{gap})" if gap and gap != "0:00" else ""
                lines.append(f"{r['rank']}. {r.get('name','?')}{gap_str}")
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

        if key == "gc_leader" or key == "gc_top5":
            gc = d.get("gc", [])
            attrs["gc_standings"] = gc
            if gc:
                leader = gc[0]
                attrs["leader_name"] = leader.get("name", "")
                attrs["leader_team"] = leader.get("team", "")
                attrs["leader_time"] = leader.get("time", "")

        if key == "status":
            attrs["race_dates"] = d.get("race_dates", "")
            attrs["total_stages"] = d.get("total_stages", 0)
            attrs["stages_completed"] = sum(1 for s in d.get("stages", []) if s.get("completed"))

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
            gc = d.get("gc", [])[:5]
            for i, rider in enumerate(gc, 1):
                attrs[f"pos_{i}_name"] = rider.get("name", "")
                attrs[f"pos_{i}_team"] = rider.get("team", "")
                attrs[f"pos_{i}_gap"] = rider.get("gap", "")

        return attrs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _race_short(race_slug: str) -> str:
    return {
        "tour-de-france": "TDF",
        "giro-d-italia": "GIRO",
        "vuelta-a-espana": "VUELTA",
    }.get(race_slug, race_slug.upper())


def _status_label(status: str) -> str:
    return {
        "not_started": "Not started",
        "live": "Live",
        "finished": "Finished",
        "unknown": "Unknown",
    }.get(status, status)


def _stage_num(stage_dict: dict) -> str:
    if not stage_dict:
        return ""
    num = stage_dict.get("stage_number", "")
    # Extract numeric part
    import re
    m = re.search(r"\d+", str(num))
    return m.group() if m else ""
