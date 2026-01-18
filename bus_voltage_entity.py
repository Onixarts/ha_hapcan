from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity import EntityCategory
from decimal import Decimal, ROUND_HALF_UP
from .hapcan_entity import HapcanEntity

class BusVoltageSensorEntity(HapcanEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.VOLTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "V"
    _attr_suggested_display_precision = 1
    _attr_icon = "mdi:flash"

    def __init__(self, device):
        HapcanEntity.__init__(self, device)
        SensorEntity.__init__(self)

        self._attr_name = "bus voltage"
        self._attr_unique_id = f"{device.id}_bus_voltage"

    def __repr__(self):
        return (
            f"<BusVoltageSensorEntity unique_id={self._attr_unique_id!r} "
            f"name={self._attr_name!r} "
            f"device={self._device.id!r}>"
        )


    #---------------------------------------------------------------------------
    # ENTITY PROPERTIES AND METHODS
    #---------------------------------------------------------------------------

    @property
    def native_value(self):
        if self._device.bus_voltage is None:
            return None
        return round(self._device.bus_voltage, 1)
