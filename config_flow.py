"""Config flow for Grand Cycling Tours."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_RACES,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    RACE_GIRO,
    RACE_TDF,
    RACE_VUELTA,
    RACE_NAMES,
)

RACE_OPTIONS = {
    RACE_TDF: RACE_NAMES[RACE_TDF],
    RACE_GIRO: RACE_NAMES[RACE_GIRO],
    RACE_VUELTA: RACE_NAMES[RACE_VUELTA],
}


class GrandCyclingToursConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Grand Cycling Tours."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle initial setup step."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors = {}

        if user_input is not None:
            if not user_input.get(CONF_RACES):
                errors[CONF_RACES] = "no_races_selected"
            else:
                return self.async_create_entry(
                    title="Grand Cycling Tours",
                    data=user_input,
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_RACES, default=[RACE_TDF, RACE_GIRO, RACE_VUELTA]): vol.All(
                    cv_multi_select(RACE_OPTIONS)
                ),
                vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=60)
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return GrandCyclingToursOptionsFlow(config_entry)


class GrandCyclingToursOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_races = self.config_entry.data.get(CONF_RACES, list(RACE_OPTIONS.keys()))
        current_interval = self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        schema = vol.Schema(
            {
                vol.Required(CONF_RACES, default=current_races): cv_multi_select(RACE_OPTIONS),
                vol.Optional(CONF_SCAN_INTERVAL, default=current_interval): vol.All(
                    vol.Coerce(int), vol.Range(min=5, max=60)
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)


def cv_multi_select(options: dict):
    """Voluptuous validator for multi-select."""
    import homeassistant.helpers.config_validation as cv
    return cv.multi_select(options)
