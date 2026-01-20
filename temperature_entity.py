import logging
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature

from .hapcan_entity import HapcanEntity

_LOGGER = logging.getLogger(__name__)


class TemperatureSensorEntity(HapcanEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_suggested_display_precision = 1

    def __init__(self, device):
        HapcanEntity.__init__(self, device)
        SensorEntity.__init__(self)

        self._attr_name = "Temperature"
        self._attr_unique_id = f"{device.id}_temperature"

    def __repr__(self):
        return f"<TemperatureSensorEntity {self._attr_unique_id}>"


    #---------------------------------------------------------------------------
    # ENTITY PROPERTIES AND METHODS
    #---------------------------------------------------------------------------

    @property
    def native_value(self):
        if self._device.temperature is None:
            return None
        return round(self._device.temperature, 1)
        
