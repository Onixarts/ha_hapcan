from homeassistant.components.cover import (
    CoverEntity,
    CoverDeviceClass,
    CoverEntityFeature,
)
from .hapcan_entity import HapcanEntity

class BlindEntity(HapcanEntity, CoverEntity):

    _attr_has_entity_name = True
    _attr_device_class = CoverDeviceClass.SHUTTER
    _attr_supported_features = (
        CoverEntityFeature.OPEN |
        CoverEntityFeature.CLOSE |
        CoverEntityFeature.STOP |
        CoverEntityFeature.SET_POSITION
    )

    def __init__(self, device, channel):
        HapcanEntity.__init__(self, device)
        CoverEntity.__init__(self)
        self._channel = channel

        self._attr_name = f"Cover channel {channel}"
        self._attr_unique_id = f"{device.id}_cover_channel_{channel}"

    def __repr__(self):
        return (
            f"<BlindEntity unique_id={self._attr_unique_id!r} "
            f"name={self._attr_name!r} "
            f"device={self._device.id!r} "
            f"channel={self._channel}>"
        )

    # ---------------------------------------------------------------------------
    # ENTITY PROPERTIES AND METHODS
    # ---------------------------------------------------------------------------

    @property
    def current_cover_position(self):
        try:
            return self._device._state[self._channel]["current_cover_position"]
        except Exception:
            return 100

    @property
    def is_closed(self):
        try:
            return self._device._state[self._channel]["is_closed"]
        except Exception:
            return False

    @property
    def is_opening(self):
        try:
            return self._device._state[self._channel]["is_opening"]
        except Exception:
            return False

    @property
    def is_closing(self):
        try:
            return self._device._state[self._channel]["is_closing"]
        except Exception:
            return False

    async def async_open_cover(self, **kwargs):
        await self._device.open(self._channel)

    async def async_close_cover(self, **kwargs):
        await self._device.close(self._channel)

    async def async_stop_cover(self, **kwargs):
        await self._device.stop(self._channel)