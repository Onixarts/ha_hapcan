import logging

from homeassistant.components.event import EventDeviceClass, EventEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class IRRemoteEventEntity(EventEntity):
    """Single IR remote represented as a HA event entity."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:remote"
    _attr_should_poll = False
    _attr_device_class = EventDeviceClass.BUTTON
    _attr_name = "Button pressed"
    _attr_translation_key = "button_pressed"

    def __init__(
        self,
        device,
        *,
        module_id: str,
        code_type: int,
        address: int,
        title: str,
        buttons: dict | None = None,
        via_device_id: str,
    ):
        EventEntity.__init__(self)
        self._device = device
        self._via_device_id = via_device_id

        self.module_id = module_id or device.id
        self.code_type = int(code_type)
        self.address = int(address)
        self.button_names = {str(k): str(v) for k, v in (buttons or {}).items()}

        self._remote_title = title or f"IR Remote {self.module_id}"
        self._attr_unique_id = f"{self.module_id}_{self.code_type}_{self.address}"
        self._attr_event_types = list(self.button_names.values()) or ["button"]

    def __repr__(self):
        return (
            f"<IRRemoteEventEntity unique_id={self._attr_unique_id!r} "
            f"name={self._attr_name!r} "
            f"module_id={self.module_id!r} "
            f"code_type={self.code_type!r} "
            f"address={self.address!r}>"
        )

    @property
    def event_types(self):
        return list(self._attr_event_types)

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, f"ir_remote_{self.module_id}_{self.code_type}_{self.address}")},
            "name": self._remote_title,
            "manufacturer": "HAPCAN",
            "model": "IR Remote",
            "via_device_id": self._via_device_id,
        }

    def update_buttons(self, buttons: dict | None):
        self.button_names = {str(k): str(v) for k, v in (buttons or {}).items()}
        self._attr_event_types = list(self.button_names.values()) or ["button"]
        if self.hass is not None:
            self.async_write_ha_state()

    def update_title(self, title: str):
        self._remote_title = title

    def handle_command(self, command, protocol):
        command_key = str(command)
        event_type = self.button_names.get(command_key)
        if event_type is None:
            _LOGGER.debug(
                "Ignoring IR command %s for remote %s (%s/%s): button not learned",
                command,
                self._remote_title,
                self.code_type,
                self.address,
            )
            return

        event_data = {
            "button": event_type,
            "command": command,
            "address": self.address,
            "protocol": protocol,
            "code_type": self.code_type,
        }
        self._trigger_event(event_type, event_data)
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._device.register_remote(self)

    async def async_will_remove_from_hass(self):
        self._device.unregister_remote(self)
        await super().async_will_remove_from_hass()
