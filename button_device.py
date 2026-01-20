import logging
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .hapcan_device import HapcanDevice
from .button_event_entity import ButtonEventEntity
from .temperature_entity import TemperatureSensorEntity
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
    0xFE: "short_press",
    0xFD: "long_press",
    0xFC: "short_click",
    0xFB: "long_click",
    0xFA: "very_long_click"
    }


class ButtonDevice(HapcanDevice):

    def __init__(self, node, group, gateway):
        super().__init__(node, group, gateway)
        self.button_count = 0

        self.temperature = None
        self._temperature_entity = None
        
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
        elif self.application_version == 1:
            self.button_count = 13
        elif self.application_version == 2:
            self.button_count = 6
        elif self.application_version == 3:
            self.button_count = 14
        else:
            _LOGGER.warning( " Unknown button application version %s for device %s", self.application_version, self )
            self.button_count = 0

        self.entities.setdefault("event", [])

        # --- BUTTONS ENTITIES ---
        existing = { e._channel: e for e in self.entities["event"] if hasattr(e, "_channel") }

        # utwórz brakujące encje
        for ch in range(1, self.button_count + 1):
            if ch not in existing:
                ent = ButtonEventEntity(self, ch)
                self.entities["event"].append(ent)
                _LOGGER.debug(" event entity created: %s", ent)


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
            entity = self.entities["event"][channel - 1]
            hass = self.gateway._hass

            hass.loop.call_soon_threadsafe(
                hass.async_create_task,
                entity.async_fire_event(press_type)
            )
        except IndexError:
            _LOGGER.error("Button channel %s out of range for device %s", channel, self)


    # -------------------------------------------------------------------------
    #  KOMPLETNOŚĆ URZĄDZENIA
    # -------------------------------------------------------------------------

    def is_complete(self) -> bool:
        if not super().is_complete():
            return False

        return True