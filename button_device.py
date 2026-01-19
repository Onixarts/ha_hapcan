import logging
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .hapcan_device import HapcanDevice
from .event_entity import HapcanEventEntity
from .const import HARDWARE_TYPE_UNIV1, HARDWARE_TYPE_UNIV3, HARDWARE_TYPE_HAPCANUINO

_LOGGER = logging.getLogger(__name__)


BUTTON_APPLICATION_VERSION = {
    0: "8 CHANNEL DIN RAIL BOX BUTTON",
    1: "13 CHANNEL BACK BOX BUTTON",
    2: "6 CHANNEL BACK BOX TOUCH BUTTON",
    3: "14 CHANNEL BACK BOX BUTTON",
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
        
        self._unsub_301 = async_dispatcher_connect( gateway._hass, "hapcan_frame_301", self._handle_button_frame_301 )


    async def async_will_remove_from_hass(self):
        if self._unsub_301:
            self._unsub_301()


    @property
    def application_type_string(self):
        return BUTTON_APPLICATION_VERSION.get( self.application_version, "Unknown button module" )

    # -------------------------------------------------------------------------
    #  TWORZENIE ENCJI
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

        # znajdź istniejące encje
        existing = { e._channel: e for e in self.entities["event"] if hasattr(e, "_channel") }

        # utwórz brakujące encje
        for ch in range(1, self.button_count + 1):
            if ch not in existing:
                ent = HapcanEventEntity(self, ch)
                self.entities["event"].append(ent)
                _LOGGER.debug(" event entity created: %s", ent)

    # -------------------------------------------------------------------------
    #  OBSŁUGA RAMEK PRZYCISKÓW (0x301)
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
            self._notify_button_event(channel, press_type)

    # -------------------------------------------------------------------------
    #  POWIADAMIANIE ENCJI
    # -------------------------------------------------------------------------

    def _notify_button_event(self, channel, press_type):
        try:
            entity = next( e for e in self.entities["event"] if getattr(e, "_channel", None) == channel)
        except StopIteration:
            _LOGGER.error( "Button channel %s not found for device %s", channel, self )
            return

        hass = self.gateway._hass

        hass.loop.call_soon_threadsafe(
            hass.async_create_task,
            entity.async_fire_event(press_type)
        )

    # -------------------------------------------------------------------------
    #  KOMPLETNOŚĆ URZĄDZENIA
    # -------------------------------------------------------------------------

    def is_complete(self) -> bool:
        if not super().is_complete():
            return False

        return True