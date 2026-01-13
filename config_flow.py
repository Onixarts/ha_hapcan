from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN


class HapcanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for HAPCAN integration."""

    VERSION = 1
    MINOR_VERSION = 0

    async def async_step_user(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(
                title="HAPCAN Gateway",
                data=user_input,
            )

        schema = vol.Schema({
            vol.Required("host", default="192.168.0.100"): str,
            vol.Required("port", default=1000): int,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )