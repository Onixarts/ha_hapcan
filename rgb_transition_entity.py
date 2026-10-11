import logging

from homeassistant.components.number import NumberEntity, NumberMode
from .hapcan_entity import HapcanEntity
from homeassistant.const import EntityCategory


_LOGGER = logging.getLogger(__name__)


class RGBTransitionEntity(HapcanEntity, NumberEntity):
    """Entity for controlling RGB default transition time"""
    
    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER
    _attr_entity_category = EntityCategory.CONFIG
    _attr_min_value = 0
    _attr_max_value = 255
    _attr_step = 1
    _attr_icon = "mdi:timer-sand"
    _attr_unit_of_measurement = "s"
    
    def __init__(self, device):
        HapcanEntity.__init__(self, device)
        NumberEntity.__init__(self)
        
        self._attr_name = "Transition"
        self._attr_unique_id = f"{device.id}_rgb_transition"
    
    def __repr__(self):
        return (
            f"<RGBTransitionEntity unique_id={self._attr_unique_id!r} "
            f"name={self._attr_name!r} "
            f"device={self._device.id!r}>"
        )
    
    # ---------------------------------------------------------------------------
    # ENTITY PROPERTIES
    # ---------------------------------------------------------------------------
    
    @property
    def native_value(self) -> float:
        """Return the current default transition time in seconds"""
        return self._device._default_transition
    
    # ---------------------------------------------------------------------------
    # ENTITY COMMANDS
    # ---------------------------------------------------------------------------
    
    async def async_set_native_value(self, value: float) -> None:
        """Set the default transition time"""
        self._device._default_transition = value
        _LOGGER.debug("RGB default transition set to %.1f seconds", value)
        self.async_write_ha_state()
