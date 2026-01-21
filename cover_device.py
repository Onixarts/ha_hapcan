import logging
from .hapcan_device import HapcanDevice
from .blind_entity import BlindEntity
from .const import (
    HARDWARE_TYPE_UNIV1,
    HARDWARE_TYPE_UNIV3,
    HARDWARE_TYPE_HAPCANUINO,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

_LOGGER = logging.getLogger(__name__)

COVER_APPLICATION_VERSION = {
    0: "3 x BLIND CONTROLLER for AC MOTORS",
}


class CoverDevice(HapcanDevice):

    def __init__(self, node, group, gateway):
        super().__init__(node, group, gateway)

        self._state = {
            channel: { 
                "current_cover_position": 100,
                "is_closed": False, 
                "is_closing": False, 
                "is_opening": False}
            for channel in (1,2,3)
        }

        self._unsub_307 = async_dispatcher_connect( gateway._hass, "hapcan_frame_307", self._handle_cover_frame_307
        )

    async def async_will_remove_from_hass(self):
        if self._unsub_307:
            self._unsub_307()

    @property
    def application_type_string(self):
        return COVER_APPLICATION_VERSION.get(self.application_version, "Unknown cover")

    # ---------------------------------------------------------
    #  CREATE ENTITIES
    # ---------------------------------------------------------

    def _create_entities(self):
        _LOGGER.debug("Creating cover entities for device %s", self)

        existing = {e._channel: e for e in self.entities["cover"]}

        for channel in (1,2,3):
            if channel not in existing:
                entity = BlindEntity(self, channel)
                self.entities["cover"].append(entity)
                _LOGGER.debug(" cover entity created: %s", entity)

    def notify_entities(self, channel):
        for ent in self.entities["cover"]:
            if ent._channel == channel:
                ent.device_updated()
                return
        _LOGGER.error("Channel %s not found for device %s", channel, self)


    # ---------------------------------------------------------
    #  Sterowanie roletą
    # ---------------------------------------------------------

    async def open(self, channel: int):
        frame = self._build_control_frame(action=1, channel=channel)
        await self.gateway.send(frame)

    async def close(self, channel: int):
        frame = self._build_control_frame(action=2, channel=channel)
        await self.gateway.send(frame)

    async def stop(self, channel: int):
        frame = self._build_control_frame(action=0, channel=channel)
        await self.gateway.send(frame)

    # ---------------------------------------------------------
    #  Budowanie ramek sterujących
    # ---------------------------------------------------------

    def _build_control_frame(self, action: int, channel: int) -> bytes:

        frame = bytearray([ 0xAA, 0x10, 0xA0, 0xF0, 0xF0, 0xFF, 0xFF, self.node, self.group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5 ])

        frame[5] = action
        frame[6] = 1 << (channel -1)
        frame[9] = 0x00 # delay

        return bytes(frame)

    # ---------------------------------------------------------
    #  Interpretacja ramek statusowych
    # ---------------------------------------------------------

    def _handle_cover_frame_307(self, msg):
        if msg.node != self.node or msg.group != self.group:
            return

        frame = msg.frame
        channel = frame[7]
        status = frame[8]   # estimated blind status (0x00-0xFF): 0x00 – blind open, 0xFF – blind closed 
        move = frame[9]     # 0x00 – blind stopped, 0x01 – going down, 0x02 – going up 

        if channel not in (1,2,3):
            return

        state = self._state[channel]
        state["current_cover_position"] = 100 - round(status * 100 / 255)

        state["is_closed"] = state["current_cover_position"] < 10
        state["is_closing"] = move == 0x01
        state["is_opening"] = move == 0x02

        self.notify_entities(channel)

    # ---------------------------------------------------------
    #  Kompletność urządzenia
    # ---------------------------------------------------------

    def is_complete(self) -> bool:
        if not super().is_complete():
            return False
        return True