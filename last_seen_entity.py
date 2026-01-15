from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import callback

class LastSeenSensorEntity(SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-time-eight-outline"

    def __init__(self, device):
        super().__init__()

        self._device = device
        self._attr_name = "last seen"
        self._attr_unique_id = f"{device.id}_last_seen"


    @property
    def native_value(self):
        return self._device.last_seen

    @property
    def device_info(self):
        return self._device.device_info

    @callback
    def device_updated(self):
        self.hass.loop.call_soon_threadsafe(self.async_write_ha_state)

    async def async_added_to_hass(self):
        await self._device.entity_ready(self)

    def __repr__(self):
        return (
            f"<LastSeenEntity unique_id={self._attr_unique_id!r} "
            f"name={self._attr_name!r} "
            f"device={self._device.id!r}>"
        )
