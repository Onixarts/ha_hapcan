import asyncio
import logging
import re

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

try:
    from homeassistant.config_entries import ConfigSubentryFlow
except ImportError:  # pragma: no cover - compatibility with older HA releases
    ConfigSubentryFlow = None

from .const import (
    CONF_ADDRESS,
    CONF_BUTTONS,
    CONF_CODE_TYPE,
    CONF_MODULE_ID,
    DOMAIN,
    DEFAULT_DIAGNOSTIC_SCAN_INTERVAL_MINUTES,
    DEFAULT_GROUP_START,
    DEFAULT_GROUP_END,
    SUBENTRY_TYPE_IR_REMOTE,
    get_ir_device_by_module_id,
)
from .ir_device import IRDevice

_LOGGER = logging.getLogger(__name__)


#-------------------------------------------------------------------------------
# CONFIG FLOW
#-------------------------------------------------------------------------------

if ConfigSubentryFlow is not None:
    class IRRemoteSubentryFlow(ConfigSubentryFlow):
        """Configure IR remotes as config subentries."""

        def __init__(self):
            self._capture_task = None
            self._module_id = None
            self._remote_name = None
            self._code_type = None
            self._address = None
            self._protocol = None
            self._command = None
            self._match = None
            self._buttons = {}
            self._is_reconfigure = False
            self._reconfigure_entry = None
            self._reconfigure_subentry = None

        # ---------------------------------------------------------------------
        # ADD REMOTE
        # ---------------------------------------------------------------------

        async def async_step_user(self, user_input=None):
            entry = self._get_entry()
            devices = self._available_ir_devices(entry)
            if not devices:
                return self.async_abort(reason="no_ir_module")

            errors = {}
            if user_input is not None:
                selected_module = user_input.get(CONF_MODULE_ID)
                if len(devices) == 1:
                    selected_module = next(iter(devices))
                if selected_module not in devices:
                    errors["base"] = "no_ir_module"
                elif not user_input.get("name", "").strip():
                    errors["name"] = "invalid_name"
                else:
                    self._module_id = selected_module
                    self._remote_name = user_input["name"].strip()
                    return await self.async_step_learn_identify()

            schema = {
                vol.Required("name"): str,
            }
            if len(devices) > 1:
                options = [
                    {
                        "value": module_id,
                        "label": f"{device.description or 'IR receiver'} ({device.node}, {device.group})",
                    }
                    for module_id, device in devices.items()
                ]
                schema[vol.Required(CONF_MODULE_ID)] = selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            else:
                self._module_id = next(iter(devices))

            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(schema),
                errors=errors,
            )

        async def async_step_learn_identify(self, user_input=None):
            return self._capture_step("learn_identify", match=None)

        async def async_step_learn_identify_done(self, user_input=None):
            result = self._consume_capture_result()
            if not isinstance(result, dict):
                if result is None:
                    return self.async_show_form(
                        step_id="learn_identify",
                        errors={"base": "capture_timeout"},
                    )
                return result

            self._code_type = result[CONF_CODE_TYPE]
            self._address = result[CONF_ADDRESS]
            self._protocol = result["protocol"]
            unique_id = self._remote_unique_id
            if any(
                getattr(subentry, "unique_id", None) == unique_id
                for subentry in self._get_entry().subentries.values()
            ):
                return self.async_abort(reason="already_configured")
            return await self.async_step_learn_button()

        # ---------------------------------------------------------------------
        # LEARN BUTTONS
        # ---------------------------------------------------------------------

        async def async_step_learn_button(self, user_input=None):
            return self._capture_step(
                "learn_button", match=(self._code_type, self._address)
            )

        async def async_step_learn_button_done(self, user_input=None):
            result = self._consume_capture_result()
            if not isinstance(result, dict):
                if result is None:
                    # Timeout. A progress step cannot hold any buttons, so when
                    # something is already learned, let the user choose what to
                    # do next (learn another one or finish) instead of looping.
                    if self._buttons:
                        return await self.async_step_more_buttons()
                    return self.async_show_form(
                        step_id="learn_button",
                        errors={"base": "capture_timeout"},
                    )
                return result

            self._command = result["command"]
            self._protocol = result["protocol"]
            return await self.async_step_name_button()

        async def async_step_name_button(self, user_input=None):
            command = str(self._command)
            current_name = self._buttons.get(command, f"button_{command}")
            errors = {}
            if user_input is not None:
                button_name = user_input.get("button", "").strip()
                if not button_name or not re.fullmatch(r"[a-z0-9_]+", button_name):
                    errors["button"] = "invalid_button_name"
                elif button_name in {
                    name for key, name in self._buttons.items() if key != command
                }:
                    errors["button"] = "button_name_exists"
                else:
                    self._buttons[command] = button_name
                    return await self.async_step_more_buttons()

            schema = vol.Schema({vol.Required("button", default=current_name): str})
            return self.async_show_form(
                step_id="name_button",
                data_schema=schema,
                errors=errors,
                description_placeholders={
                    "command": command,
                    "protocol": self._protocol or "",
                },
            )

        async def async_step_more_buttons(self, user_input=None):
            """Menu shown after each learned button: learn next or finish."""
            return self.async_show_menu(
                step_id="more_buttons",
                menu_options=["learn_button", "finish"],
                description_placeholders={"count": str(len(self._buttons))},
            )

        async def async_step_finish(self, user_input=None):
            """Save the remote (create a new subentry or update the existing one)."""
            data = {
                CONF_MODULE_ID: self._module_id,
                CONF_CODE_TYPE: self._code_type,
                CONF_ADDRESS: self._address,
                "protocol": self._protocol,
                CONF_BUTTONS: self._buttons,
            }
            if self._is_reconfigure:
                return self.async_update_and_abort(
                    self._reconfigure_entry,
                    self._reconfigure_subentry,
                    title=self._remote_name,
                    data=data,
                )
            return self.async_create_entry(
                title=self._remote_name,
                data=data,
                unique_id=self._remote_unique_id,
            )

        # ---------------------------------------------------------------------
        # RECONFIGURE
        # ---------------------------------------------------------------------

        async def async_step_learn_more(self, user_input=None):
            entry_id = self._get_entry().entry_id
            entry_data = self.hass.data.get(DOMAIN, {}).get(
                entry_id, {}
            )
            if not isinstance(
                get_ir_device_by_module_id(
                    entry_data.get("devices", {}), self._module_id
                ),
                IRDevice,
            ):
                return self.async_abort(reason="no_ir_module")
            return await self.async_step_learn_button()

        async def async_step_reconfigure(self, user_input=None):
            self._is_reconfigure = True
            self._reconfigure_entry = self._get_entry()
            self._reconfigure_subentry = self._get_reconfigure_subentry()
            subentry = self._reconfigure_subentry
            self._module_id = subentry.data[CONF_MODULE_ID]
            self._code_type = int(subentry.data[CONF_CODE_TYPE])
            self._address = int(subentry.data[CONF_ADDRESS])
            self._protocol = subentry.data.get("protocol", "Unknown")
            self._buttons = {
                str(command): str(name)
                for command, name in subentry.data.get(CONF_BUTTONS, {}).items()
            }
            self._remote_name = subentry.title
            return self.async_show_menu(
                step_id="reconfigure",
                menu_options=["edit_buttons", "learn_more"],
            )

        async def async_step_edit_buttons(self, user_input=None):
            errors = {}
            schema = vol.Schema({
                vol.Optional(command, default=name): str
                for command, name in self._buttons.items()
            })
            if user_input is not None:
                updated = {
                    command: value.strip()
                    for command, value in user_input.items()
                    if value.strip()
                }
                names = list(updated.values())
                if any(not re.fullmatch(r"[a-z0-9_]+", name) for name in names):
                    errors["base"] = "invalid_button_name"
                elif len(names) != len(set(names)):
                    errors["base"] = "button_name_exists"
                else:
                    data = dict(self._reconfigure_subentry.data)
                    data[CONF_MODULE_ID] = self._module_id
                    data[CONF_BUTTONS] = updated
                    return self.async_update_and_abort(
                        self._reconfigure_entry,
                        self._reconfigure_subentry,
                        title=self._remote_name,
                        data=data,
                    )
            return self.async_show_form(
                step_id="edit_buttons",
                data_schema=schema,
                errors=errors,
            )

        # ---------------------------------------------------------------------
        # CAPTURE HELPERS
        # ---------------------------------------------------------------------

        def _capture_step(self, step_id, *, match):
            if self._capture_task is None:
                entry_data = self.hass.data.get(DOMAIN, {}).get(
                    self._get_entry().entry_id, {}
                )
                device = get_ir_device_by_module_id(
                    entry_data.get("devices", {}), self._module_id
                )
                if not isinstance(device, IRDevice):
                    return self.async_abort(reason="no_ir_module")
                self._match = match
                self._capture_task = self.hass.async_create_task(
                    device.async_capture_code(timeout=30, match=match),
                    name="hapcan_ir_remote_capture",
                )

            if not self._capture_task.done():
                return self.async_show_progress(
                    step_id=step_id,
                    progress_action=step_id,
                    progress_task=self._capture_task,
                )

            return self.async_show_progress_done(next_step_id=f"{step_id}_done")

        def _consume_capture_result(self):
            try:
                result = self._capture_task.result()
            except asyncio.CancelledError:
                self._capture_task = None
                return self.async_abort(reason="capture_cancelled")
            except Exception:
                _LOGGER.exception("Failed to capture IR remote code")
                self._capture_task = None
                return self.async_abort(reason="capture_failed")
            self._capture_task = None
            return result

        def _available_ir_devices(self, entry):
            devices = self.hass.data.get(DOMAIN, {}).get(entry.entry_id, {}).get("devices", {})
            return {
                device.id: device
                for device in devices.values()
                if isinstance(device, IRDevice)
            }

        @property
        def _remote_unique_id(self):
            return f"{self._module_id}_{self._code_type}_{self._address}"

        @callback
        def async_remove(self) -> None:
            """Flow closed (e.g. dialog dismissed): stop waiting for an IR code.

            Cancelling the task makes IRDevice.async_capture_code clean up and
            lift the learning mode (event suppression) on the module.
            """
            if self._capture_task is not None and not self._capture_task.done():
                self._capture_task.cancel()
            self._capture_task = None


class HapcanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for HAPCAN integration."""

    VERSION = 1
    MINOR_VERSION = 0

    @classmethod
    @callback
    def async_get_supported_subentry_types(cls, config_entry):
        if ConfigSubentryFlow is None:
            return {}
        return {SUBENTRY_TYPE_IR_REMOTE: IRRemoteSubentryFlow}

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
