import logging

from homeassistant.components.event import EventEntity
from .hapcan_entity import HapcanEntity
from .const import HapcanEvent

_LOGGER = logging.getLogger(__name__)


class IREventEntity(HapcanEntity, EventEntity):
    """HAPCAN IR receiver represented as an event entity."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:eye-arrow-left"
    _attr_event_types = [ HapcanEvent.IR_CODE_RECEIVED ]

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