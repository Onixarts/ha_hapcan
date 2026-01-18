import logging
from .hapcan_device import HapcanDevice
from .relay_entity import RelayEntity
from .const import HARDWARE_TYPE_UNIV1, HARDWARE_TYPE_UNIV3, HARDWARE_TYPE_HAPCANUINO
from homeassistant.helpers.dispatcher import async_dispatcher_connect


_LOGGER = logging.getLogger(__name__)

RELAY_APPLICATION_VERSION = {
    1: "6 x 5A MONOSTABLE RELAY",
    2: "6 x 5A BISTABLE RELAY",
    3: "6 x 16A MONOSTABLE RELAY",
    4: "6 x 16A BISTABLE RELAY",
    5: "6 x 6A MONOSTABLE RELAY"
}

class RelayDevice(HapcanDevice):
    """
    Urządzenie HAPCAN typu Relay (applicationType = 0x02).
    """
    APPLICATION_TYPE = 0x02

    def __init__(self, node, group, gateway):
        super().__init__(node, group, gateway)
        
        # stan kanałów (True/False)
        self._state = [False] * 6

        self._unsub_302 = async_dispatcher_connect( gateway._hass, "hapcan_frame_302", self._handle_status_frame_302 )


    async def async_will_remove_from_hass(self):
        if self._unsub_302:
            self._unsub_302()

    @property
    def application_type_string(self):
        return RELAY_APPLICATION_VERSION.get(self.application_version, "Unknown relay")

    def _create_entities(self):
        _LOGGER.debug("Creating specific entities for device %s", self)

        existing = {e._channel: e for e in self.entities["switch"]}

        for channel in range(1, 7):
            if channel not in existing:
                entity = RelayEntity(self, channel)
                self.entities["switch"].append(entity)
                _LOGGER.debug(" entity created: %s", entity)
        

    def notify_entities(self, channel):
        try:
            entity = self.entities["switch"][channel - 1]
            entity.device_updated()
        except IndexError:
            _LOGGER.error("Channel %s out of range for device %s", channel, self)

    # ---------------------------------------------------------
    #  Sterowanie odpowiednim kanałem urządzenia
    # ---------------------------------------------------------

    async def turn_on(self, channel: int):
        #self._state[channel] = True
        frame = self._build_control_frame(action=1, channels_mask=1 << (channel - 1))
        await self.gateway.send(frame)

    async def turn_off(self, channel: int):
        frame = self._build_control_frame(action=0, channels_mask=1 << (channel - 1))
        await self.gateway.send(frame)

    async def toggle(self, channel: int):
        frame = self._build_control_frame(action=2, channels_mask=1 << (channel - 1))
        await self.gateway.send(frame)

    # ---------------------------------------------------------
    #  Budowanie ramek sterujących
    # ---------------------------------------------------------

    def _build_control_frame(self, action: int, channels_mask: int, delay: int = 0x00) -> bytes:
        """
        Buduje ramkę sterującą 0x10A
        """
        frame = bytearray([ 0xAA, 0x10, 0xA0, 0xF0, 0xF0, 0xFF, 0xFF, self.node, self.group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5 ])


        if self.hardware_type == HARDWARE_TYPE_UNIV1:
            frame[10] = action
            frame[11] = channels_mask
            frame[12] = delay
        elif self.hardware_type in (HARDWARE_TYPE_UNIV3, HARDWARE_TYPE_HAPCANUINO):
            frame[5] = action
            frame[6] = channels_mask
            frame[9] = delay
        else:
            _LOGGER.warning("Unknown hardware type %s for %s", self.hardware_type, self)

        return bytes(frame)

    # ---------------------------------------------------------
    #  Interpretacja ramek informacyjnych
    # ---------------------------------------------------------

    def _handle_status_frame_302(self, msg):
        node = msg.node
        group = msg.group
        frame = msg.frame

        if msg.node != self.node or msg.group != self.group:
            return

        channel = frame[7]
        if not (1 <= channel <= 6):
            return

        state = frame[8] != 0x00
        self._state[channel - 1] = state

        self.notify_entities(channel)

    # ---------------------------------------------------------
    #  Kompletność urządzenia
    # ---------------------------------------------------------

    def is_complete(self) -> bool:
        if not super().is_complete():
            return False
        
        return True