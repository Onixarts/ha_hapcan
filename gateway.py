import asyncio
import logging

from homeassistant.helpers import device_registry as dr
from homeassistant.core import HomeAssistant
from .message import HapcanMessage
from .hapcan_device import HapcanDevice
from . import const
from .const import DOMAIN
from .relay_device import RelayDevice
from .button_device import ButtonDevice
from .cover_device import CoverDevice
from .rgb_device import RGBDevice
from .ir_device import IRDevice
from homeassistant.helpers.dispatcher import async_dispatcher_send, async_dispatcher_connect
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta


_LOGGER = logging.getLogger(__name__)

DEVICE_CLASS_REGISTRY = {
    const.APPLICATION_TYPE_RELAY: RelayDevice,
    const.APPLICATION_TYPE_BUTTON: ButtonDevice,
    const.APPLICATION_TYPE_BLIND_CONTROLLER: CoverDevice,
    const.APPLICATION_TYPE_LED_CONTROLLER: RGBDevice,
    const.APPLICATION_TYPE_IR_TRANSMITTER: IRDevice,
}

# ----------------------------------------------------------------------------------------------
# HAPCAN GATEWAY
# ----------------------------------------------------------------------------------------------

class HapcanGateway:
    """Gateway TCP dla HAPCAN z odbiorem ramek 13/15 bajtów."""
    SENDING_LIMIT = 0.01

    def __init__(self, hass: HomeAssistant, entry_id, options):
        self._hass = hass
        self._host = options["host"]
        self._port = options["port"]
        self._group_start = int(options["group_start"])
        self._group_end = int(options["group_end"])
        self.entry_id = entry_id

        self._reader = None
        self._writer = None
        self.connected = False
        self._stopped = False
        self._connection_task = None
        self._scan_task = None

        self._sending_buffer = []
        self._sending_task = None
        self._unsubscribers = []

        self._incoming = bytearray([0xFF] * 16)
        self._index = 0
        self._description_index = 0

        self._unsubscribers.append(async_dispatcher_connect(hass, "hapcan_frame_103", self._on_response_device_id_from_group_0x103))
        self._unsubscribers.append(async_dispatcher_connect(hass, "hapcan_frame_106", self._on_firmware_response_0x106))
        self._unsubscribers.append(async_dispatcher_connect(hass, "hapcan_frame_10e", self._on_description_response_0x10E))

        if options["diagnostic_scan_interval_minutes"] > 0:
            self._unsubscribers.append(
                async_track_time_interval(
                    hass,
                    self._poll_voltage,
                    timedelta(minutes=options["diagnostic_scan_interval_minutes"]),
                )
            )


    async def connect(self):
        """Uruchamia pętlę utrzymującą połączenie TCP."""
        if self._connection_task and not self._connection_task.done():
            return

        self._stopped = False
        self._connection_task = asyncio.create_task(self._connection_loop())

    async def _connection_loop(self):
        retry_delay = 1

        while not self._stopped:
            connected_at = None
            try:
                self._reader, self._writer = await asyncio.open_connection(
                    self._host, self._port
                )
                self.connected = True
                connected_at = self._hass.loop.time()
                _LOGGER.info("HAPCAN connected to %s:%s", self._host, self._port)

                self._scan_task = asyncio.create_task(self.scan_network())
                await self._read_loop()

            except asyncio.CancelledError:
                raise
            except Exception:
                _LOGGER.exception("HAPCAN connection error to %s:%s", self._host, self._port)
            finally:
                self.connected = False
                if self._scan_task:
                    self._scan_task.cancel()
                    await asyncio.gather(self._scan_task, return_exceptions=True)
                    self._scan_task = None

                self._sending_buffer.clear()
                if self._sending_task:
                    self._sending_task.cancel()
                    await asyncio.gather(self._sending_task, return_exceptions=True)
                    self._sending_task = None

                await self._close_writer()

            if self._stopped:
                break

            if connected_at is not None and self._hass.loop.time() - connected_at >= 30:
                retry_delay = 1

            _LOGGER.warning("HAPCAN disconnected; retrying in %s seconds", retry_delay)
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 60)

    async def _close_writer(self):
        writer = self._writer
        self._writer = None
        self._reader = None
        if writer is None:
            return

        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass

    async def stop(self):
        """Zatrzymuje połączenie i zwalnia zasoby gatewaya."""
        self._stopped = True
        self.connected = False

        tasks = [self._connection_task, self._scan_task, self._sending_task]
        for task in tasks:
            if task and not task.done():
                task.cancel()

        await self._close_writer()
        await asyncio.gather(
            *(task for task in tasks if task and task is not asyncio.current_task()),
            return_exceptions=True,
        )

        self._connection_task = None
        self._scan_task = None
        self._sending_task = None
        self._sending_buffer.clear()

        entry_data = self._hass.data.get(DOMAIN, {}).get(self.entry_id)
        if entry_data:
            for device in entry_data["devices"].values():
                device.cleanup()

        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()

    async def _read_loop(self):
        
        while self.connected and not self._stopped:
            try:
                data = await self._reader.read(64)
                if not data:
                    _LOGGER.warning("HAPCAN TCP connection closed by peer")
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
                            _LOGGER.debug("RECV << %s", msg)
                            if msg.frame_type == 0x10e:
                                self._description_index += 1
                                msg.description_index = self._description_index

                            signal = f"hapcan_frame_{msg.frame_type:03x}"
                            async_dispatcher_send(self._hass, signal, msg)

                            device = self._hass.data[DOMAIN][self.entry_id]["devices"].get((msg.node, msg.group))
                            if device:
                                device.update_last_seen()
                        else:
                            _LOGGER.warning(
                                "Unknown frame received: %s", self._incoming[:self._index+1].hex()
                            )
                        self._reset_buffer()
                        continue

                    self._index += 1

            except Exception as e:
                _LOGGER.error("Receiving error: %s", e)
                self.connected = False
                break

    def _reset_buffer(self):
        self._incoming = bytearray([0xFF] * 16)
        self._index = 0


    # ----------------------------------------------------------------------------------------------
    # SKANOWANIE SIECI HAPCAN
    # ----------------------------------------------------------------------------------------------

    async def scan_network(self, progress_callback=None):
        _LOGGER.debug("HAPCAN BUS SCANNING...")

        for group in range(self._group_start, self._group_end + 1):
            if progress_callback is not None:
                await progress_callback(group)

            frame = bytearray([0xAA, 0x10, 0x30, 0x00, 0x00, 0xFF, 0xFF, 0x00, group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5])

            _LOGGER.debug("Scanning group %s ------------------------------------------", group)
            await self.send(frame)

            # mały odstęp, żeby nie zalać magistrali
            await asyncio.sleep(2.0)



    def _on_response_device_id_from_group_0x103(self, msg):
        node = msg.node
        group = msg.group
        frame = msg.frame

        _LOGGER.debug("Device id response (0x103) for (%s, %s)", node, group)
        _LOGGER.debug(" (%s, %s): searching devices list...", node, group)
        device = self._hass.data[DOMAIN][self.entry_id]["devices"].get((msg.node, msg.group))

        # create device if is None
        if device is None:
            _LOGGER.debug(" (%s, %s): not found, creating <HapcanDevice>", node, group)

            self._hass.data[DOMAIN][self.entry_id]["devices"][(node, group)] = HapcanDevice(node, group, self)
            device = self._hass.data[DOMAIN][self.entry_id]["devices"][(node, group)]

            serial = (frame[9] << 24) | (frame[10] << 16) | (frame[11] << 8) | frame[12]
            device.serial_number = f"0x{serial:08X}"

            device.hardware_type = (frame[5] << 8) | frame[6]

            _LOGGER.debug(" (%s, %s): device created in list %s", node, group, device)
        else:
            _LOGGER.debug(" (%s, %s): found %s", node, group, device)

        self.request_firmware(node, group)


    def request_firmware(self, node, group):
        _LOGGER.debug("Requesting firmware from (%s, %s)", node, group)
        frame = bytes([ 0xAA, 0x10, 0x60, 0x00, 0x00, 0xFF, 0xFF, node, group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5 ])
        
        self._hass.loop.call_soon_threadsafe(
            asyncio.create_task,
            self.send(frame)
        )
        

    def _on_firmware_response_0x106(self, msg):
        _LOGGER.debug("Firmware response (0x106) for (%s, %s)", msg.node, msg.group)
        device = self._hass.data[DOMAIN][self.entry_id]["devices"].get((msg.node, msg.group))
        if device is None:
            _LOGGER.error(" (%s, %s) not found in device list", msg.node, msg.group)
            return
        frame = msg.frame

        device.hardware_version = frame[7]
        device.application_type = frame[8]
        device.application_version = frame[9]
        device.firmware_version = frame[10]

        _LOGGER.debug(" (%s, %s): device firmware updated %s", msg.node, msg.group, device)
        self._update_device(device)

        device.reset_description()

        self.request_description(msg.node, msg.group)


    def request_description(self, node, group):
        _LOGGER.debug("Requesting description from (%s, %s)", node, group)
        frame = bytes([ 0xAA, 0x10, 0xE0, 0x00, 0x00, 0xFF, 0xFF, node, group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5])

        self._hass.loop.call_soon_threadsafe(
            asyncio.create_task,
            self.send(frame)
        )


    def _on_description_response_0x10E(self, msg):
        _LOGGER.debug("Description response for (%s, %s)", msg.node, msg.group)
        device = self._hass.data[DOMAIN][self.entry_id]["devices"].get((msg.node, msg.group))
        if device is None:
            _LOGGER.error(" (%s, %s) not found in device list", msg.node, msg.group)
            return

        frame = msg.frame
        chunk_bytes = bytes(frame[5:13])
        chunk = chunk_bytes.split(b"\x00", 1)[0].decode("ascii", errors="ignore")


        if device._description_chunks[0] is None:
            device._description_chunks[0] = chunk
            device._description_chunks_index[0] = msg.description_index
            _LOGGER.debug(" (%s, %s): description chunk 1 received: '%s', index=%s", msg.node, msg.group, chunk, msg.description_index)

        else:
            device._description_chunks[1] = chunk
            device._description_chunks_index[1] = msg.description_index
            _LOGGER.debug(" (%s, %s): description chunk 2 received: '%s', index=%s", msg.node, msg.group, chunk, msg.description_index)


        if all(chunk is not None for chunk in device._description_chunks):
            if device._description_chunks_index[0] < device._description_chunks_index[1]:
                device.description = device._description_chunks[0] + device._description_chunks[1]
            else:
                device.description = device._description_chunks[1] + device._description_chunks[0]
            
            _LOGGER.debug(" (%s, %s): description updated: '%s'", msg.node, msg.group, device.description)

            self._update_device(device)

    async def _poll_voltage(self, now):
        _LOGGER.debug("Pooling voltage from devices")
        devices = self._hass.data[DOMAIN][self.entry_id]["devices"]
        for device in devices.values():
            try:
                await device.request_voltage()
                await asyncio.sleep(0.02)
            except Exception as e:
                _LOGGER.error(" Voltage poll failed for device %s", device, e)

#---------------------------------------------------------------------------------------
# HA DEVICE AND ENTITIES MANAGEMENT
#---------------------------------------------------------------------------------------

    def _update_device(self, device):
        node = device.node
        group = device.group
        
        _LOGGER.debug("Updating device: %s", device )
        
        if not device:
            _LOGGER.error(" Updating device failed. Device is None.")
            return
        
        # try changing the device class when it is base HapcanDevice class
        if type(device) is HapcanDevice:
            _LOGGER.debug(" Changing device class: %s", device )
            device_class = DEVICE_CLASS_REGISTRY.get(device.application_type, None)
            
            if device_class:
                device.cleanup()
                new_device = device_class.from_existing(device)
                self._hass.data[DOMAIN][self.entry_id]["devices"][(node, group)] = new_device
                device = new_device
                _LOGGER.debug(" Device class changed: %s", device )
            else:
                _LOGGER.warning(" Device is not supported %s", device)

        if device.is_complete():
            #self._register_device_in_ha(device)

            _LOGGER.debug(" Hapcan device ready: %s", device)
            self._hass.loop.call_soon_threadsafe(
                async_dispatcher_send,
                self._hass,
                f"hapcan_device_ready_{self.entry_id}",
                device
            )
        else:
            _LOGGER.debug(" Device info not complete yet (%s)", device )
            

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
            _LOGGER.debug("SEND >> %s", HapcanMessage(payload))
            self._writer.write(payload)


    async def _sending_loop(self):
        try:
            while self._sending_buffer:
                payload = self._sending_buffer.pop(0)
                self._internal_send(payload)
                await asyncio.sleep(self.SENDING_LIMIT)

        finally:
            # koniec wysyłania
            self._sending_task = None


    async def send(self, payload: bytes):

        if not self.connected:
            _LOGGER.error("HAPCAN not connected")
            return

        # zamieniamy na bytearray, bo będziemy modyfikować checksum
        self._sending_buffer.append(bytearray(payload))

        if self._sending_task is None:
            self._sending_task = asyncio.create_task(self._sending_loop())