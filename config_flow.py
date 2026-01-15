from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_DIAGNOSTIC_SCAN_INTERVAL_MINUTES


#-------------------------------------------------------------------------------
# CONFIG FLOW
#-------------------------------------------------------------------------------

class HapcanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for HAPCAN integration."""

    VERSION = 1
    MINOR_VERSION = 0

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="HAPCAN Gateway",
                data={
                    "host": user_input["host"],
                    "port": user_input["port"],
                    "diagnostic_scan_interval_minutes": DEFAULT_DIAGNOSTIC_SCAN_INTERVAL_MINUTES,  

                },
            )

        schema = vol.Schema({
            vol.Required("host", default="192.168.0.100"): str,
            vol.Required("port", default=1000): int,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return HapcanOptionsFlow(config_entry)


#-------------------------------------------------------------------------------
# OPTIONS FLOW
#-------------------------------------------------------------------------------

class HapcanOptionsFlow(config_entries.OptionsFlow):
    """Options flow to edit config after installation."""

    def __init__(self, config_entry):
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # zapisujemy zmienione wartości w options
            return self.async_create_entry(
                title="",
                data={
                    "host": user_input["host"],
                    "port": user_input["port"],
                    "diagnostic_scan_interval_minutes": user_input["diagnostic_scan_interval_minutes"],
                },
            )

        # aktualne wartości (options > data > default)
        current_host = self.config_entry.options.get(
            "host", self.config_entry.data.get("host", "192.168.0.100")
        )
        current_port = self.config_entry.options.get(
            "port", self.config_entry.data.get("port", 1000)
        )
        current_interval = self.config_entry.options.get(
            "diagnostic_scan_interval_minutes",
            self.config_entry.data.get("diagnostic_scan_interval_minutes", DEFAULT_DIAGNOSTIC_SCAN_INTERVAL_MINUTES)
        )

        schema = vol.Schema({
            vol.Required("host", default=current_host): str,
            vol.Required("port", default=current_port): int,
            vol.Required("diagnostic_scan_interval_minutes", default=current_interval): vol.All(
                vol.Coerce(int),
                vol.Range(min=0, max=1440)
            ),
        })

        return self.async_show_form(step_id="init", data_schema=schema)

