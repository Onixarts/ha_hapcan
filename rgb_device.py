import logging

from .hapcan_device import HapcanDevice
from .rgb_entity import RgbEntity, RGBChannel
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

RGB_APPLICATION_VERSION = {
    0: "RGB LED CONTROLLER",
}

class RGBDevice(HapcanDevice):

    def __init__(self, node, group, gateway):
        super().__init__(node, group, gateway)

        self._states = [0] * 4
        self._on = False

        self._rgb_entity = None


        self._unsub_308 = async_dispatcher_connect( gateway._hass, "hapcan_frame_308", self._handle_rgb_frame_308 )

    async def async_will_remove_from_hass(self):
        if self._unsub_308:
            self._unsub_308()

    @property
    def application_type_string(self):
        return RGB_APPLICATION_VERSION.get(self.application_version, "Unknown RGB")

    # ---------------------------------------------------------
    #  CREATE ENTITIES
    # ---------------------------------------------------------

    def _create_entities(self):
        _LOGGER.debug("Creating RGB entities for device %s", self)

        # RGB entity
        if self._rgb_entity is None:
            self._rgb_entity = RgbEntity(self)
            self.entities["light"].append(self._rgb_entity)
            _LOGGER.debug(" RGB entity created: %s", self._rgb_entity)

        # single channel entities


    def notify_entities(self, channel):

        self._rgb_entity.device_updated()
        _LOGGER.debug("dupa updated %s", channel)

        # for ent in self.entities["light"]:
        #     if ent._channel == channel:
        #         ent.device_updated()
        #         return

        #_LOGGER.error("Channel %s not found for device %s", channel, self)

    # ---------------------------------------------------------
    #  SENDING COMMANDS
    # ---------------------------------------------------------

    async def set_rgb(self, r: int, g: int, b: int, brightness: int, transition: int):

        frame = self._build_rgb_frame(r, g, b, brightness, transition)
        await self.gateway.send(frame)

    # ---------------------------------------------------------
    #  BUILD CONTROL FRAME
    # ---------------------------------------------------------

    def _build_rgb_frame(self, r: int, g: int, b: int, brightness: int, transition: int) -> bytes:

        frame = bytearray([ 0xAA, 0x10, 0xA0, 0xF0, 0xF0, 0xFF, 0xFF, self.node, self.group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5 ])

        action = 0x20 #SET RGB TO

        frame[5] = action
        frame[6] = r
        frame[9] = g
        frame[10] = b
        frame[11] = 0x00 # timer

        return bytes(frame)

    # ---------------------------------------------------------
    #  HANDLE STATUS FRAME
    # ---------------------------------------------------------

    def _handle_rgb_frame_308(self, msg):
        if msg.node != self.node or msg.group != self.group:
            return

        frame = msg.frame
        channel = frame[7]

        if channel not in (1, 2, 3, 4):
            return

        state = frame[8]
        self._states[channel-1] = state


        if channel == RGBChannel.MASTER.value:
            self._on = False if frame[9] == 0x00 else True
        
            
        _LOGGER.debug("dupa chanel=%s relay %s", channel, frame[9])
        _LOGGER.debug("dupa ON=%s", self._on)

        self.notify_entities(channel)

    # ---------------------------------------------------------
    #  COMPLETENESS CHECK
    # ---------------------------------------------------------

    def is_complete(self) -> bool:
        if not super().is_complete():
            return False
        return True