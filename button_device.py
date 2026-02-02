import logging
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .hapcan_device import HapcanDevice
from .button_event_entity import ButtonEventEntity
from .temperature_entity import TemperatureSensorEntity
from .button_led_entity import ButtonLedSwitchEntity
from .const import HARDWARE_TYPE_UNIV1, HARDWARE_TYPE_UNIV3, HARDWARE_TYPE_HAPCANUINO

_LOGGER = logging.getLogger(__name__)

APPLICATION_VERSION_8_CHANNEL_DIN_RAIL_BUTTON = 0
APPLICATION_VERSION_13_CHANNEL_BACK_BOX_BUTTON = 1
APPLICATION_VERSION_6_CHANNEL_BACK_BOX_TOUCH_BUTTON = 2
APPLICATION_VERSION_14_CHANNEL_BACK_BOX_BUTTON = 3


BUTTON_APPLICATION_VERSION = {
    APPLICATION_VERSION_8_CHANNEL_DIN_RAIL_BUTTON: "8 CHANNEL DIN RAIL BOX BUTTON",
    APPLICATION_VERSION_13_CHANNEL_BACK_BOX_BUTTON: "13 CHANNEL BACK BOX BUTTON",
    APPLICATION_VERSION_6_CHANNEL_BACK_BOX_TOUCH_BUTTON: "6 CHANNEL BACK BOX TOUCH BUTTON",
    APPLICATION_VERSION_14_CHANNEL_BACK_BOX_BUTTON: "14 CHANNEL BACK BOX BUTTON",
}

BUTTON_CODE_TO_EVENT = {
    0x00: "open",
    0x01: "disabled",
    0xFF: "closed",
    0xFE: "closed_held_400ms",
    0xFD: "closed_held_4s",
    0xFC: "closed_opened_within_400ms",
    0xFB: "closed_opened_between_400ms_4s",
    0xFA: "closed_opened_after_4s",
    }


class ButtonDevice(HapcanDevice):

    def __init__(self, node, group, gateway):
        super().__init__(node, group, gateway)
        self.button_count = 0

        self.temperature = None
        self._temperature_entity = None
        self.led_states = []
        
        self._unsub_301 = async_dispatcher_connect( gateway._hass, "hapcan_frame_301", self._handle_button_frame_301 )

        #TODO don't subscribe if device has no temperature sensor
        self._unsub_304 = async_dispatcher_connect( gateway._hass, "hapcan_frame_304", self._handle_temperature_frame_304 )


    async def async_will_remove_from_hass(self):
        if self._unsub_301:
            self._unsub_301()
        if self._unsub_304:
            self._unsub_304()


    @property
    def application_type_string(self):
        return BUTTON_APPLICATION_VERSION.get( self.application_version, "Unknown button module" )

    # -------------------------------------------------------------------------
    #  ENTITIES
    # -------------------------------------------------------------------------

    def _create_entities(self):
        _LOGGER.debug("Creating button entities for device %s", self)


        if self.application_version == 0:
            self.button_count = 8
            self.led_states = []
        elif self.application_version == 1:
            self.button_count = 13
            self.led_states = [None] * 13
        elif self.application_version == 2:
            self.button_count = 6
            self.led_states = [None] * 6
        elif self.application_version == 3:
            self.button_count = 14
            self.led_states = [None] * 14
        else:
            _LOGGER.warning( " Unknown button application version %s for device %s", self.application_version, self )
            self.button_count = 0

        self.entities.setdefault("event", [])
        self.entities.setdefault("switch", [])

        # --- BUTTONS ENTITIES ---
        existing = { e._channel: e for e in self.entities["event"] if hasattr(e, "_channel") }

        # utwórz brakujące encje
        for ch in range(1, self.button_count + 1):
            if ch not in existing:
                ent = ButtonEventEntity(self, ch)
                self.entities["event"].append(ent)
                _LOGGER.debug(" event entity created: %s", ent)

        # --- LED ENTITIES ---
        existing = { e._channel: e for e in self.entities["switch"] if hasattr(e, "_channel") }

        for ch in range(1, len(self.led_states) + 1):
            if ch not in existing:
                ent = ButtonLedSwitchEntity(self, ch)
                self.entities["switch"].append(ent)
                _LOGGER.debug(" switch entity created: %s", ent)

        # --- TEMPERATURE  ---
        if self.application_version != APPLICATION_VERSION_8_CHANNEL_DIN_RAIL_BUTTON:

            self.entities.setdefault("sensor", [])

            if self._temperature_entity is None:
                self._temperature_entity = TemperatureSensorEntity(self)
                self.entities["sensor"].append(self._temperature_entity)
                _LOGGER.debug(" entity created: %s", self._temperature_entity)


    # -------------------------------------------------------------------------
    #  FRAME HANDLING
    # -------------------------------------------------------------------------

    def _handle_button_frame_301(self, msg):
        if msg.node != self.node or msg.group != self.group:
            return

        frame = msg.frame
        channel = frame[7]

        if not (1 <= channel <= self.button_count):
            return

        if self.application_version != APPLICATION_VERSION_8_CHANNEL_DIN_RAIL_BUTTON:
            led_state = frame[9]
            #if led_state != 0x01:
            self.led_states[channel - 1] = led_state
            #else:
                #_LOGGER.debug(" led %s is disabled in device %s", channel, self)

        press_type = BUTTON_CODE_TO_EVENT.get(frame[8], None)

        if press_type:
            self.notify_entities(channel, press_type)

        
    
    
    def _handle_temperature_frame_304(self, msg):
        
        if self.application_version == APPLICATION_VERSION_8_CHANNEL_DIN_RAIL_BUTTON:
            return
        if msg.node != self.node or msg.group != self.group:
            return

        frame = msg.frame

        # temperature frame
        if frame[7] != 0x11:
            return
        
        raw_temp = (frame[8] << 8) | frame[9]
        self.temperature = round(raw_temp * 0.0625, 1)

        if self._temperature_entity:
            self._temperature_entity.device_updated()


    # -------------------------------------------------------------------------
    #  NOTIFY ENTITIES
    # -------------------------------------------------------------------------

    def notify_entities(self, channel, press_type):
        try:
            button_entity = self.entities["event"][channel - 1]
            hass = self.gateway._hass

            hass.loop.call_soon_threadsafe(
                hass.async_create_task,
                button_entity.async_fire_event(press_type)
            )

            if self.application_version != APPLICATION_VERSION_8_CHANNEL_DIN_RAIL_BUTTON:
                led_entity = self.entities["switch"][channel - 1]
                led_entity.device_updated()

        except IndexError:
            _LOGGER.error("Button or led channel %s out of range for device %s", channel, self)

    # ---------------------------------------------------------
    #  DEVICE CONTROL
    # ---------------------------------------------------------

    async def turn_on(self, channel: int):
        frame = self._build_control_frame(action=1, channels_mask=1 << (channel - 1))
        if self.application_version != APPLICATION_VERSION_8_CHANNEL_DIN_RAIL_BUTTON:
            if self._update_led_state_local(channel, 0xFF):
                await self.gateway.send(frame)

    async def turn_off(self, channel: int):
        frame = self._build_control_frame(action=0, channels_mask=1 << (channel - 1))
        if self.application_version != APPLICATION_VERSION_8_CHANNEL_DIN_RAIL_BUTTON:
            if self._update_led_state_local(channel, 0x00):
                await self.gateway.send(frame)

    async def toggle(self, channel: int):
        frame = self._build_control_frame(action=2, channels_mask=1 << (channel - 1))
        if self.application_version != APPLICATION_VERSION_8_CHANNEL_DIN_RAIL_BUTTON:
            current = self.led_states[channel - 1]
            new_state = 0x00 if current == 0xFF else 0xFF
            if self._update_led_state_local(channel, new_state):
                await self.gateway.send(frame)


    def _update_led_state_local(self, channel: int, new_state: int): 
        idx = channel - 1
        old = self.led_states[idx]

        if old == 0x01:
            _LOGGER.warning("LED %s is disabled in device %s", channel, self)
            return False

        self.led_states[idx] = new_state

        # notify entity
        for ent in self.entities.get("switch", []):
            if ent._channel == channel:
                ent.device_updated()
        
        return True

    # ---------------------------------------------------------
    #  CONTROL FRAME
    # ---------------------------------------------------------

    def _build_control_frame(self, action: int, channels_mask: int, delay: int = 0x00) -> bytes:
        """
        Buduje ramkę sterującą 0x10A
        """
        frame = bytearray([ 0xAA, 0x10, 0xA0, 0xF0, 0xF0, 0xFF, 0xFF, self.node, self.group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5 ])

        frame[5] = action
        frame[6] = channels_mask & 0xFF
        frame[9] = (channels_mask >> 8) & 0xFF

        return bytes(frame)

    # -------------------------------------------------------------------------
    #  KOMPLETNOŚĆ URZĄDZENIA
    # -------------------------------------------------------------------------

    def is_complete(self) -> bool:
        if not super().is_complete():
            return False

        return True