from homeassistant.core import callback
from homeassistant.helpers.entity import Entity

class HapcanEntity(Entity):
    """Base class for all Hapcan entities."""

    def __init__(self, device):
        super().__init__()
        self._device = device
        self.registered = False

    @property
    def device_info(self):
        return self._device.device_info

    @callback
    def device_updated(self):
        if self.hass is not None:
            self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    async def async_added_to_hass(self):
        await self._device.entity_ready(self)