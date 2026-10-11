import logging

from .hapcan_device import HapcanDevice
from .rgb_entity import RgbEntity, RGBChannel
from .rgb_channel_entity import RGBChannelEntity
from .rgb_transition_entity import RGBTransitionEntity
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
        self._default_transition = 0  # domyślnie bez przejścia

        self._rgb_entity = None
        self._channel_entities = {}
        self._transition_entity = None

        self._unsub_308 = async_dispatcher_connect( gateway._hass, "hapcan_frame_308", self._handle_rgb_frame_308 )

    async def async_will_remove_from_hass(self):
        self.cleanup()

    def cleanup(self):
        super().cleanup()
        if self._unsub_308:
            self._unsub_308()
            self._unsub_308 = None

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
        for channel in range(1, 5):
            if channel not in self._channel_entities:
                entity = RGBChannelEntity(self, channel)
                self._channel_entities[channel] = entity
                self.entities["light"].append(entity)
                _LOGGER.debug(" RGB channel entity created: %s", entity)

        # transition time entity
        if self._transition_entity is None:
            self._transition_entity = RGBTransitionEntity(self)
            self.entities["number"].append(self._transition_entity)
            _LOGGER.debug(" RGB transition entity created: %s", self._transition_entity)


    def notify_entities(self, channel):

        self._rgb_entity.device_updated()
        
        if channel in self._channel_entities:
            self._channel_entities[channel].device_updated()
        

    # ---------------------------------------------------------
    #  SENDING COMMANDS
    # ---------------------------------------------------------

    async def set_rgb(self, r: int, g: int, b: int, brightness: int, transition: int = None):

        if transition is None:
            transition = int(self._default_transition)
        else:
            transition = int(transition)
        
        frame = bytearray([ 0xAA, 0x10, 0xA0, 0xF0, 0xF0, 0xFF, 0xFF, self.node, self.group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5 ])


        if transition == 0:
            action = 0x20 #SET RGB TO… instant
        else:
            trasition_frame = bytearray([ 0xAA, 0x10, 0xA0, 0xF0, 0xF0, 0xFF, 0xFF, self.node, self.group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5 ])
            trasition_frame[5] = 0x22  # SET RGB SPEED TO… 
            trasition_frame[6] = transition - 1
            await self.gateway.send(trasition_frame)
            action = 0x21  #SET RGB TO… soft

        frame[5] = action
        frame[6] = r
        frame[9] = g
        frame[10] = b
        frame[11] = 0x00 # timer

        await self.gateway.send(frame)


    async def set_channel(self, channel: int, brightness: int, transition: int = None):
        """Set brightness for a single channel"""
        if transition is None:
            _LOGGER.debug("transition is none")
            transition = int(self._default_transition)
        else:
            _LOGGER.debug("transition is %s", transition)
            transition = int(transition)
        
        if channel < 1 or channel > 4:
            _LOGGER.error("Invalid RGB channel: %s. Channel must be 1-4", channel)
            raise ValueError(f"Invalid RGB channel: {channel}. Channel must be 1-4")
        
        frame = bytearray([ 0xAA, 0x10, 0xA0, 0xF0, 0xF0, 0xFF, 0xFF, self.node, self.group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5 ])
        
        # Determine command based on transition (0 = instant, > 0 = soft)
        if transition == 0:
            action = 0x00 + channel - 1  # instant action: 0x00, 0x01, 0x02, 0x03
            _LOGGER.debug("action set to instant: %s", action)
        else:
            trasition_frame = bytearray([ 0xAA, 0x10, 0xA0, 0xF0, 0xF0, 0xFF, 0xFF, self.node, self.group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5 ])
            trasition_frame[5] = 0x22  # SET RGB SPEED TO… 
            trasition_frame[6] = transition - 1
            _LOGGER.debug("action set to soft, sending transition frame first:")
            await self.gateway.send(trasition_frame)

            action = 0x0F + channel  # soft action: 0x10, 0x11, 0x12, 0x13
            _LOGGER.debug("action set to soft: %s", action)
        
        frame[5] = action
        frame[6] = brightness
        frame[9] = 0x00 # timer
        _LOGGER.debug('ustaw RGB channel: %s, brightness=%s, transtion=%s', channel, brightness, transition)

        await self.gateway.send(frame)

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
           
        self.notify_entities(channel)

    # ---------------------------------------------------------
    #  COMPLETENESS CHECK
    # ---------------------------------------------------------

    def is_complete(self) -> bool:
        if not super().is_complete():
            return False
        return True

