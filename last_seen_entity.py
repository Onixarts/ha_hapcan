from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.entity import EntityCategory
from .hapcan_entity import HapcanEntity

class LastSeenSensorEntity(HapcanEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-time-eight-outline"

    def __init__(self, device):
        HapcanEntity.__init__(self, device)
        SensorEntity.__init__(self)

        self._attr_name = "last seen"
        self._attr_unique_id = f"{device.id}_last_seen"

    def __repr__(self):
        return (
            f"<LastSeenEntity unique_id={self._attr_unique_id!r} "
            f"name={self._attr_name!r} "
            f"device={self._device.id!r}>"
        )

    #---------------------------------------------------------------------------
    # ENTITY PROPERTIES AND METHODS
    #---------------------------------------------------------------------------

    @property
    def native_value(self):
        return self._device.last_seen