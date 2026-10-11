import logging

from homeassistant.components.light import (
    LightEntity,
    ColorMode,
    ATTR_BRIGHTNESS,
    ATTR_TRANSITION,
    LightEntityFeature
)

from .hapcan_entity import HapcanEntity

_LOGGER = logging.getLogger(__name__)

CHANNEL_NAMES = {
    1: "Red",
    2: "Green", 
    3: "Blue",
    4: "Master"
}


class RGBChannelEntity(HapcanEntity, LightEntity):
    """Entity for controlling individual RGB channels"""
    
    _attr_has_entity_name = True
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_features = LightEntityFeature.TRANSITION
    
    def __init__(self, device, channel: int):
        HapcanEntity.__init__(self, device)
        LightEntity.__init__(self)
        
        self._channel = channel
        
        self._attr_name = CHANNEL_NAMES.get(channel, f"Channel {channel}")
        self._attr_unique_id = f"{device.id}_rgb_channel_{channel}"
    
    def __repr__(self):
        return (
            f"<RGBChannelEntity unique_id={self._attr_unique_id!r} "
            f"name={self._attr_name!r} "
            f"channel={self._channel!r} "
            f"device={self._device.id!r}>"
        )
    
    # ---------------------------------------------------------------------------
    # ENTITY PROPERTIES
    # ---------------------------------------------------------------------------
    
    @property
    def is_on(self):
        return self._device._states[self._channel - 1] > 0
    
    @property
    def brightness(self):
        return self._device._states[self._channel - 1]
    
    # ---------------------------------------------------------------------------
    # ENTITY COMMANDS
    # ---------------------------------------------------------------------------
    
    async def async_turn_on(self, **kwargs):
        if ATTR_BRIGHTNESS in kwargs:
            brightness = kwargs[ATTR_BRIGHTNESS]
        else:
            brightness = self._device._states[self._channel - 1] or 255
        
        if ATTR_TRANSITION in kwargs:
            transition = kwargs.get(ATTR_TRANSITION)
        else:
            transition = None
        
        await self._device.set_channel(self._channel, brightness, transition=transition)
    
    async def async_turn_off(self, **kwargs):
        if ATTR_TRANSITION in kwargs:
            transition = kwargs.get(ATTR_TRANSITION)
        else:
            transition = None
        
        await self._device.set_channel(self._channel, 0, transition=transition)
