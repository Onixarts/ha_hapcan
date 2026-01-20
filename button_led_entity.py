from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from .hapcan_entity import HapcanEntity

class ButtonLedSwitchEntity(HapcanEntity, SwitchEntity):

    _attr_has_entity_name = True
    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_icon = "mdi:led-off"

    def __init__(self, device, channel):
        HapcanEntity.__init__(self, device)
        SwitchEntity.__init__(self)
        self._channel = channel

        #TODO dodać tutaj nazwy z ramki 0x117
        self._attr_name = f"Button led {channel}"
        self._attr_unique_id = f"{device.id}_button_led_channel_{channel}"

    @property
    def icon(self):
        state = self._device.led_states[self._channel - 1]
        if state == 0xFF:
            return "mdi:led-on"
        if state == 0x00:
            return "mdi:led-off"
        return "mdi:led-variant-off"

    @property
    def available(self):
        return self._device.led_states[self._channel - 1] != 0x01

    def __repr__(self):
        return (
            f"<ButtonLedSwitchEntity unique_id={self._attr_unique_id!r} "
            f"name={self._attr_name!r} "
            f"device={self._device.id!r} "
            f"channel={self._channel}>"
        )


    #---------------------------------------------------------------------------
    # ENTITY PROPERTIES AND METHODS
    #---------------------------------------------------------------------------

    @property
    def is_on(self):
        try:
            return self._device.led_states[self._channel-1] == 0xFF
        except Exception:
            return False

    async def async_turn_on(self, **kwargs):
        await self._device.turn_on(self._channel)

    async def async_turn_off(self, **kwargs):
        await self._device.turn_off(self._channel)

    async def async_toggle(self, **kwargs):
        await self._device.toggle(self._channel)

