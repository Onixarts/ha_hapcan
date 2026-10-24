import logging

from homeassistant.util.color import value_to_brightness
from enum import Enum

from homeassistant.components.light import (
    LightEntity,
    ColorMode,
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION
)

from .hapcan_entity import HapcanEntity

_LOGGER = logging.getLogger(__name__)
BRIGHTNESS_SCALE = (1, 1023)
class RGBChannel(Enum):
    RED = 1
    GREEN = 2
    BLUE = 3
    MASTER = 4

class RgbEntity(HapcanEntity, LightEntity):

    _attr_has_entity_name = True
    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB

    def __init__(self, device):
        HapcanEntity.__init__(self, device)
        LightEntity.__init__(self)

        self._attr_name = f"RGB"
        self._attr_unique_id = f"{device.id}_rgb"

    def __repr__(self):
        return (
            f"<RgbEntity unique_id={self._attr_unique_id!r} "
            f"name={self._attr_name!r} "
            f"device={self._device.id!r}>"
        )

    # ---------------------------------------------------------------------------
    # ENTITY PROPERTIES
    # ---------------------------------------------------------------------------

    @property
    def is_on(self):
        return self._device._on

    @property
    def brightness(self):
        return value_to_brightness(BRIGHTNESS_SCALE, self._device._states[RGBChannel.MASTER.value - 1])

    @property
    def rgb_color(self):
        device = self._device
        return (device._states[RGBChannel.RED.value - 1], device._states[RGBChannel.GREEN.value - 1], device._states[RGBChannel.BLUE.value - 1] )

    # ---------------------------------------------------------------------------
    # ENTITY COMMANDS
    # ---------------------------------------------------------------------------

    async def async_turn_on(self, **kwargs):
        r = g = b = None

        _LOGGER.debug("kwargs=%s", kwargs)

        if ATTR_RGB_COLOR in kwargs and kwargs[ATTR_RGB_COLOR] is not None:
            rgb = kwargs[ATTR_RGB_COLOR]
            if isinstance(rgb, (tuple, list)) and len(rgb) == 3:
                r, g, b = rgb

        if r is None or g is None or b is None:
            last_rgb = self._device._states[0:3]
            r = last_rgb[0] if last_rgb[0] is not None else 0
            g = last_rgb[1] if last_rgb[1] is not None else 0
            b = last_rgb[2] if last_rgb[2] is not None else 0

        brightness = self._device._states[RGBChannel.MASTER.value - 1] or 255

        if ATTR_TRANSITION in kwargs:
            transition = kwargs.get(ATTR_TRANSITION) or 0
        else:
            transition = 0

        await self._device.set_rgb(r, g, b, brightness, transition=transition)

    
    async def async_turn_off(self, **kwargs):
        await self._device.set_rgb(0, 0, 0, 0)