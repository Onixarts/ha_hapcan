import logging

from homeassistant.components.event import EventEntity, EventDeviceClass
from .hapcan_entity import HapcanEntity

_LOGGER = logging.getLogger(__name__)


class ButtonEventEntity(HapcanEntity, EventEntity):
    """HAPCAN physical button represented as an event entity."""

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_has_entity_name = True
    _attr_event_types = [
        "open",
        "disabled",
        "closed", 
        "short_press",
        "long_press", 
        "short_click",
        "long_click",
        "very_long_click" 
    ]

    def __init__(self, device, channel):
        HapcanEntity.__init__(self, device)
        EventEntity.__init__(self)

        self._channel = channel

        # TODO: nazwy z ramki 0x117
        self._attr_name = f"Button {channel}"
        self._attr_unique_id = f"{device.id}_button_{channel}"

    def __repr__(self):
        return (
            f"<ButtonEventEntity unique_id={self._attr_unique_id!r} "
            f"name={self._attr_name!r} "
            f"device={self._device.id!r} "
            f"channel={self._channel}>"
        )

    # ---------------------------------------------------------------------------
    # EVENT HANDLING
    # ---------------------------------------------------------------------------

    async def async_fire_event(self, press_type: str):
        """Called by device when a button event occurs."""
        if press_type not in self._attr_event_types:
            _LOGGER.warning(
                "Unknown press type %s for button %s on device %s",
                press_type, self._channel, self._device.id
            )
            return

        _LOGGER.debug("Firing event '%s' for button %s on device %s", press_type, self._channel, self._device )

        self._trigger_event(
            press_type,
            {
                "device_id": self._device.id,
                "channel": self._channel,
                "press_type": press_type,
            }
        )
        self.async_write_ha_state()


