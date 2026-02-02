import logging

from homeassistant.components.event import EventEntity
from .hapcan_entity import HapcanEntity

_LOGGER = logging.getLogger(__name__)


class IREventEntity(HapcanEntity, EventEntity):
    """HAPCAN IR receiver represented as an event entity."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:eye-arrow-left"
    _attr_event_types = [
        "hapcan.ir_code_received",
    ]

    def __init__(self, device):
        HapcanEntity.__init__(self, device)
        EventEntity.__init__(self)

        self._attr_name = "IR Code Received"
        self._attr_unique_id = f"{device.id}_ir_event"

    def __repr__(self):
        return (
            f"<IREventEntity unique_id={self._attr_unique_id!r} "
            f"name={self._attr_name!r} "
            f"device={self._device.id!r}>"
        )

    # ---------------------------------------------------------------------------
    # EVENT HANDLING
    # ---------------------------------------------------------------------------

    async def async_fire_event(self, ir_code: str, code_name: str):
        """Called by device when an IR code is received."""
        event_type = "hapcan.ir_code_received"
        event_data = {
            "device_id": self._device.id,
            "ir_code": ir_code,
            "code_name": code_name,
        }

        _LOGGER.debug("Firing event '%s' for IR code %s on device %s", event_type, ir_code, self._device)

        self._trigger_event(event_type, event_data)
        self.async_write_ha_state()
