import asyncio
import logging

from homeassistant.helpers import device_registry as dr
from homeassistant.core import HomeAssistant
from .message import HapcanMessage
from .hapcan_device import HapcanDevice
from . import const
from .const import DOMAIN
from .relay_device import RelayDevice
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.dispatcher import async_dispatcher_connect


_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_REGISTRY = {
    const.APPLICATION_TYPE_RELAY: RelayDevice
}

# ----------------------------------------------------------------------------------------------
# HAPCAN GATEWAY
# ----------------------------------------------------------------------------------------------

class HapcanGateway:
    """Gateway TCP dla HAPCAN z odbiorem ramek 13/15 bajtów."""
    SENDING_LIMIT = 0.005

    def __init__(self, hass: HomeAssistant, host: str, port: int, entry_id):
        self._hass = hass
        self._host = host
        self._port = port
        self.entry_id = entry_id

        self._reader = None
        self._writer = None
        self.connected = False

        #self.dispatcher = FrameDispatcher()
        self._sending_buffer = []
        self._sending_task = None

        self._incoming = bytearray([0xFF] * 16)
        self._index = 0

        async_dispatcher_connect(hass, "hapcan_frame_103", self._on_response_device_id_from_group_0x103)
        async_dispatcher_connect(hass, "hapcan_frame_106", self._on_firmware_response_0x106)
        async_dispatcher_connect(hass, "hapcan_frame_10e", self._on_description_response_0x10E)

    async def connect(self):
        """Nawiązanie połączenia TCP."""

        try:
            self._reader, self._writer = await asyncio.open_connection(
                self._host, self._port
            )
            self.connected = True
            _LOGGER.info("HAPCAN: Połączono z %s:%s", self._host, self._port)

            asyncio.create_task(self._read_loop())
            asyncio.create_task(self.scan_network())

        except Exception as e:
            _LOGGER.error("HAPCAN: Błąd połączenia: %s", e)
            self.connected = False

    async def _read_loop(self):
        """Odbiór ramek bajt po bajcie (jak w Twoim Node-RED)."""
        while self.connected:
            try:
                data = await self._reader.read(64)
                if not data:
                    _LOGGER.error("HAPCAN: Rozłączono")
                    self.connected = False
                    break

                for byte in data:
                    # Początek ramki musi być 0xAA
                    if self._index == 0 and byte != 0xAA:
                        continue

                    self._incoming[self._index] = byte

                    # Ramka 13 bajtów (index 12) kończy się 0xA5
                    if self._index == 12 and byte == 0xA5:
                        #self._handle_frame(self._incoming[:13])
                        self._reset_buffer()
                        continue

                    # Ramka 15 bajtów (index 14) kończy się 0xA5
                    if self._index == 14:
                        if byte == 0xA5:
                            msg = HapcanMessage(self._incoming[:15])
                            _LOGGER.debug("HAPCAN << %s", msg)
                            signal = f"hapcan_frame_{msg.frame_type:03x}"
                            async_dispatcher_send(self._hass, signal, msg)

                            device = self._hass.data[DOMAIN][self.entry_id]["devices"].get((msg.node, msg.group))
                            if device:
                                device.update_last_seen()
                            #device = self._hass.data[DOMAIN][self.entry_id]["devices"].get((msg.node, msg.group)) #can be None
                            #_LOGGER.debug("Device from cache: %s", device)
                            #self.dispatcher.dispatch(msg, device)
                        else:
                            _LOGGER.warning(
                                "HAPCAN: Niepoprawna ramka: %s", self._incoming[:self._index+1].hex()
                            )
                        self._reset_buffer()
                        continue

                    self._index += 1

            except Exception as e:
                _LOGGER.error("HAPCAN: Błąd odbioru: %s", e)
                self.connected = False
                break

    def _reset_buffer(self):
        self._incoming = bytearray([0xFF] * 16)
        self._index = 0


    # ----------------------------------------------------------------------------------------------
    # SKANOWANIE SIECI HAPCAN
    # ----------------------------------------------------------------------------------------------

    async def scan_network(self):
        """
        Skanuje wszystkie grupy 1–255 wysyłając ramkę 0x103.
        """

        for group in range(1, 2):
            frame = bytearray([0xAA, 0x10, 0x30, 0x00, 0x00, 0xFF, 0xFF, 0x00, group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5])

            await self.send(frame)

            # mały odstęp, żeby nie zalać magistrali
            await asyncio.sleep(3.00)

    def _on_response_device_id_from_group_0x103(self, msg):
        node = msg.node
        group = msg.group
        frame = msg.frame

        _LOGGER.debug("0x103 frame handler: searching cache for (%s, %s)", node, group)
        device = self._hass.data[DOMAIN][self.entry_id]["devices"].get((msg.node, msg.group))

        # create device if is None
        if device is None:
            _LOGGER.debug("0x103 frame handler: Device (%s, %s) not found in cache", node, group)
            _LOGGER.debug("0x103 frame handler: Creating HapcanDevice for (%s, %s) ", node, group)
            self._hass.data[DOMAIN][self.entry_id]["devices"][(node, group)] = HapcanDevice(node, group, self)
            device = self._hass.data[DOMAIN][self.entry_id]["devices"][(node, group)]

            serial = (frame[9] << 24) | (frame[10] << 16) | (frame[11] << 8) | frame[12]
            device.serial_number = f"0x{serial:08X}"

            device.hardware_type = (frame[5] << 8) | frame[6]

            _LOGGER.debug("0x103 frame handler: Device (%s) created in cache", device)
            self._device_discovered(device)
        else:
            _LOGGER.debug("0x103 frame handler: Device %s exists", device)

        self.request_firmware(node, group)


    def request_firmware(self, node, group):
        _LOGGER.debug("Requesting (%s, %s) for firmware", node, group)
        frame = bytes([ 0xAA, 0x10, 0x60, 0x00, 0x00, 0xFF, 0xFF, node, group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5 ])
        
        self._hass.loop.call_soon_threadsafe(
            asyncio.create_task,
            self.send(frame)
        )
        

    def _on_firmware_response_0x106(self, msg):
        _LOGGER.debug("0x106 frame handler for device (%s, %s)", msg.node, msg.group)
        device = self._hass.data[DOMAIN][self.entry_id]["devices"].get((msg.node, msg.group))
        if device is None:
            _LOGGER.error(f"Updating device failed. Device not found in device list.")
            return  # nie znamy urządzenia
        frame = msg.frame

        device.hardware_version = frame[7]
        device.application_type = frame[8]
        device.application_version = frame[9]
        device.firmware_version = frame[10]

        _LOGGER.debug("0x106 frame handler: Device %s updated from device firmware response", device)
        self._update_device(device)

        self.request_description(msg.node, msg.group)


    def request_description(self, node, group):
        _LOGGER.debug("Requesting (%s, %s) for description", node, group)
        frame = bytes([ 0xAA, 0x10, 0xE0, 0x00, 0x00, 0xFF, 0xFF, node, group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5])

        self._hass.loop.call_soon_threadsafe(
            asyncio.create_task,
            self.send(frame)
        )


    def _on_description_response_0x10E(self, msg):
        _LOGGER.debug("0x10E frame handler for device (%s, %s)", msg.node, msg.group)
        device = self._hass.data[DOMAIN][self.entry_id]["devices"].get((msg.node, msg.group))
        if device is None:
            _LOGGER.error("Description update failed. Device not found.")
            return

        frame = msg.frame
        chunk_bytes = bytes(frame[5:13])
        chunk = chunk_bytes.split(b"\x00", 1)[0].decode("ascii", errors="ignore")

        if device._desc_chunks == 0:
            device.description = chunk
            device._desc_chunks = 1
            return

        device.description += chunk

        self._update_device(device)


#---------------------------------------------------------------------------------------
# HA DEVICE AND ENTITIES MANAGEMENT
#---------------------------------------------------------------------------------------

    def _device_discovered(self, device):
        _LOGGER.debug("Device (%s, %s) discovered on Hapcan bus", device.node, device.group)


    def _update_device(self, device):
        node = device.node
        group = device.group
        
        _LOGGER.debug("Updating device: %s", device )
        
        if not device:
            _LOGGER.error("Updating device failed. Device is None.")
            return
        

        #device = hass.data[DOMAIN][entry.entry_id]["devices"][(node, group)]

        # try changing the device class when it is base HapcanDevice class
        if type(device) is HapcanDevice:
            _LOGGER.debug("Updating device. Changing class for (%s, %s)", node, group )
            device_class = DEVICE_CLASS_REGISTRY.get(device.application_type, None)
            
            if device_class:
                new_device = device_class.from_existing(device)
                self._hass.data[DOMAIN][self.entry_id]["devices"][(node, group)] = new_device
                device = new_device
                _LOGGER.debug("Device class changed: %s", device )
            else:
                _LOGGER.warning("Updating device (%s). Device is not supported.", device)


        #devices = hass.data[DOMAIN][entry.entry_id]["devices"]
        #for key, dev in devices.items():
        #   _LOGGER.info(f"Device {key}: {dev}\n")

        if device.is_complete():
            #self._register_device_in_ha(device)

            _LOGGER.debug("Notify registration")
            self._hass.loop.call_soon_threadsafe(
                async_dispatcher_send,
                self._hass,
                f"hapcan_device_ready_{self.entry_id}",
                device
            )
        else:
            _LOGGER.debug("Updating device. Device (%s) not complete for registration", device )
            

#---------------------------------------------------------------------------------------
# SENDING MESSAGES
#---------------------------------------------------------------------------------------

    def _internal_send(self, payload: bytearray):
        """Dodaje checksum i wysyła ramkę do TCP."""

        # checksum dla ramek 15 bajtowych
        if len(payload) == 15:
            checksum = sum(payload[1:13]) & 0xFF
            payload[13] = checksum

        # checksum dla ramek 13 bajtowych
        elif len(payload) == 13:
            checksum = sum(payload[1:11]) & 0xFF
            payload[11] = checksum

        if self._writer:
            _LOGGER.debug("HAPCAN >> %s", HapcanMessage(payload))
            self._writer.write(payload)

    async def _sending_loop(self):
        """Wysyła ramki z kolejki co SENDING_LIMIT sekund."""

        try:
            while self._sending_buffer:
                payload = self._sending_buffer.pop(0)
                self._internal_send(payload)
                await asyncio.sleep(self.SENDING_LIMIT)

        finally:
            # koniec wysyłania
            self._sending_task = None

    async def send(self, payload: bytes):
        """Dodaje ramkę do kolejki wysyłania."""

        if not self.connected:
            _LOGGER.error("HAPCAN: próba wysłania bez połączenia")
            return

        # zamieniamy na bytearray, bo będziemy modyfikować checksum
        self._sending_buffer.append(bytearray(payload))

        # jeśli nie ma aktywnego zadania wysyłania → startujemy
        if self._sending_task is None:
            self._sending_task = asyncio.create_task(self._sending_loop())