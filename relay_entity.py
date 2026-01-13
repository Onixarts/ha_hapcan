from homeassistant.components.switch import SwitchEntity
from homeassistant.core import callback

class RelayEntity(SwitchEntity):

    _attr_has_entity_name = True
    #_attr_icon = "mdi:toggle-switch-variant-off"

    def __init__(self, device, channel):
        self._device = device
        self._channel = channel

        #TODO dodać tutaj nazwy z ramki 0x117
        self._attr_name = f"Relay channel {channel}"
        self._attr_unique_id = f"{device.id}_relay_channel_{channel}"

    @property
    def device_info(self):
        return {
            "identifiers": {("hapcan", f"{self._device.id}")},
            "manufacturer": "HAPCAN"
        }


    @property
    def is_on(self):
        try:
            return self._device._state[self._channel-1]
        except Exception:
            return False

    async def async_turn_on(self, **kwargs):
        await self._device.turn_on(self._channel)

    async def async_turn_off(self, **kwargs):
        await self._device.turn_off(self._channel)

    async def async_toggle(self, **kwargs):
        await self._device.toggle(self._channel)

    @callback
    def device_updated(self):
        """Wywoływane przez RelayDevice, gdy stan kanału się zmieni."""
        self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    def __repr__(self):
        return (
            f"<RelayEntity unique_id={self._attr_unique_id!r} "
            f"name={self._attr_name!r} "
            f"device={self._device.id!r} "
            f"channel={self._channel}>"
        )