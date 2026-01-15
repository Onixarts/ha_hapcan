from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import EntityCategory
from homeassistant.core import callback

class CpuVoltageSensorEntity(SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "V"
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:chip"

    def __init__(self, device):
        super().__init__()

        self._device = device
        self._attr_name = "cpu voltage"
        self._attr_unique_id = f"{device.id}_cpu_voltage"

    @property
    def native_value(self):
        if self._device.cpu_voltage is None:
            return None
        return round(self._device.cpu_voltage, 1)

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
            f"<CpuVoltageSensorEntity unique_id={self._attr_unique_id!r} "
            f"name={self._attr_name!r} "
            f"device={self._device.id!r}>"
        )