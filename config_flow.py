import asyncio
import logging

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    DEFAULT_DIAGNOSTIC_SCAN_INTERVAL_MINUTES,
    DEFAULT_GROUP_START,
    DEFAULT_GROUP_END,
)

_LOGGER = logging.getLogger(__name__)


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
                    "group_start": DEFAULT_GROUP_START,
                    "group_end": DEFAULT_GROUP_END,
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
        self._scan_task = None
        self._scan_group_start = None
        self._scan_group_count = 0

    def async_abort(self, reason):
        if self._scan_task and not self._scan_task.done():
            self._scan_task.cancel()
        return super().async_abort(reason)

    # --- MENU GŁÓWNE ---
    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "edit": "Properties",
                "scan": "Scan Hapcan bus",
            }
        )

    # --- EDYCJA OPCJI ---
    async def async_step_edit(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="",
                data={
                    "host": user_input["host"],
                    "port": user_input["port"],
                    "diagnostic_scan_interval_minutes": user_input["diagnostic_scan_interval_minutes"],
                    "group_start": user_input["group_start"],
                    "group_end": user_input["group_end"],
                },
            )

        current_host = self.config_entry.options.get(
            "host", self.config_entry.data.get("host", "192.168.0.100")
        )
        current_port = self.config_entry.options.get(
            "port", self.config_entry.data.get("port", 1000)
        )
        current_interval = self.config_entry.options.get(
            "diagnostic_scan_interval_minutes",
            self.config_entry.data.get(
                "diagnostic_scan_interval_minutes",
                DEFAULT_DIAGNOSTIC_SCAN_INTERVAL_MINUTES
            )
        )
        current_group_start = self.config_entry.options.get(
            "group_start",
            self.config_entry.data.get("group_start", DEFAULT_GROUP_START),
        )
        current_group_end = self.config_entry.options.get(
            "group_end",
            self.config_entry.data.get("group_end", DEFAULT_GROUP_END),
        )
        schema = vol.Schema({
            vol.Required("host", default=current_host): str,
            vol.Required("port", default=current_port): int,
            vol.Required("group_start", default=current_group_start): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=255,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required("group_end", default=current_group_end): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=255,
                    step=1,
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                "diagnostic_scan_interval_minutes",
                default=current_interval
            ): vol.All(vol.Coerce(int), vol.Range(min=0, max=1440)),
        })

        return self.async_show_form(step_id="edit", data_schema=schema)

    # --- RĘCZNE SKANOWANIE MAGISTRALI ---
    async def async_step_scan(self, user_input=None):
        gateway = self.hass.data[DOMAIN][self.config_entry.entry_id]["gateway"]
        if self._scan_task is None:
            group_start = gateway._group_start
            group_end = gateway._group_end
            self._scan_group_start = group_start
            self._scan_group_count = group_end - group_start + 1
            self._scan_task = self.hass.async_create_task(
                self._run_scan(gateway), name="hapcan_manual_scan"
            )

        if self._scan_task.done():
            try:
                self._scan_task.result()
            except asyncio.CancelledError:
                return self.async_abort(reason="scan_cancelled")
            except Exception:
                _LOGGER.exception("HAPCAN network scan failed")
                return self.async_abort(reason="scan_failed")
            finally:
                self._scan_task = None

            return self.async_show_progress_done(next_step_id="scan_done")

        return self.async_show_progress(
            step_id="scan",
            progress_action="scan",
            progress_task=self._scan_task,
        )

    async def async_step_scan_done(self, user_input=None):
        return await self.async_step_init()

    async def _run_scan(self, gateway):
        await gateway.scan_network(self._update_scan_progress)

    async def _update_scan_progress(self, group):
        progress = (group - self._scan_group_start + 1) / self._scan_group_count
        self.async_update_progress(progress)