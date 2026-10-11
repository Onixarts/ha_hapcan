import logging
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .hapcan_device import HapcanDevice
from .ir_event_entity import IREventEntity
from .remote_entity import RemoteEntity
from .const import HARDWARE_TYPE_UNIV1, HARDWARE_TYPE_UNIV3, HARDWARE_TYPE_HAPCANUINO, HapcanEvent

_LOGGER = logging.getLogger(__name__)

APPLICATION_VERSION_IR_RECEIVER_TRANSMITTER = 0

IR_APPLICATION_VERSION = {
    APPLICATION_VERSION_IR_RECEIVER_TRANSMITTER: "INFRARED RECEIVER & TRANSMITTER",
}

IR_CODES = {
    0x03: " SIRC 12 bit code",
    0x04: " SIRC 15 bit code",
    0x05: "SIRC 20 bit code",
    0x06: "RC5 code",
    0x07: "NEC 16 bit code",
    0x08: "NEC 24 bit code",
}

class IRDevice(HapcanDevice):

    def __init__(self, node, group, gateway):
        super().__init__(node, group, gateway)

        # Słownik do mapowania kodów IR na nazwy
        
        # Encje IR
        self._ir_event_entity = None
        self._remote_entity = None
        
        # Obsługiwane sygnały
        self._unsub_303 = async_dispatcher_connect( gateway._hass, "hapcan_frame_303", self._handle_ir_frame_303 )


    async def async_will_remove_from_hass(self):
        if self._unsub_303:
            self._unsub_303()
            self._unsub_303 = None
        self._ir_event_entity = None
        self._remote_entity = None


    @property
    def application_type_string(self):
        return IR_APPLICATION_VERSION.get( self.application_version, "Unknown IR module" )

    # -------------------------------------------------------------------------
    #  ENTITIES
    # -------------------------------------------------------------------------

    def _create_entities(self):
        _LOGGER.debug("Creating IR entities for device %s", self)

        if self.application_version not in IR_APPLICATION_VERSION:
            _LOGGER.warning( "Unknown IR application version %s for device %s", self.application_version, self )
            return

        self.entities.setdefault("event", [])
        self.entities.setdefault("remote", [])

        # --- IR EVENT ENTITY (odbieranie sygnałów) ---
        if self._ir_event_entity is None:
            self._ir_event_entity = IREventEntity(self)
            self.entities["event"].append(self._ir_event_entity)
            _LOGGER.debug(" event entity created: %s", self._ir_event_entity)

        # --- REMOTE ENTITY (wysyłanie sygnałów) ---
        if self._remote_entity is None:
            self._remote_entity = RemoteEntity(self)
            self.entities["remote"].append(self._remote_entity)
            _LOGGER.debug(" remote entity created: %s", self._remote_entity)


    # -------------------------------------------------------------------------
    # NOTIFY ENTITIES
    # -------------------------------------------------------------------------

    def notify_entities(self, address: str, command: str, protocol: str, code_type: str):
        try:
            if self._ir_event_entity is None:
                return
            
            hass = self.gateway._hass

            event_type = HapcanEvent.IR_CODE_RECEIVED
            event_data = {
                "device_id": self.id,
                "code_type": code_type,
                "address": address,
                "command": command,
                "protocol": protocol,
            }
            

            self._ir_event_entity._trigger_event(event_type, event_data)
            self._ir_event_entity.device_updated()

            hass.bus.async_fire(event_type, event_data)

        except Exception as e:
            _LOGGER.error("Error notifying IR event: %s", e)

    # -------------------------------------------------------------------------
    # FRAME HANDLING
    # -------------------------------------------------------------------------

    async def _handle_ir_frame_303(self, msg):

        if msg.node != self.node or msg.group != self.group:
            return

        frame = msg.frame
        
        # Extract code type and check if it's end of transmission
        code_type_byte = frame[7]
        is_end_transmission = (code_type_byte & 0x80) != 0
        code_type = code_type_byte & 0x7F  # Remove 0x80 flag if present
        
        code1 = frame[8]
        code2 = frame[9]
        code3 = frame[10]
        
        transmission_state = "end" if is_end_transmission else "beginning"
                
        # Only process the beginning of transmission to avoid duplicate events
        if is_end_transmission:
            return
            
        # Extract address and command based on code type
        protocol = IR_CODES.get(code_type, "Unknown").strip()
        code_type_hex = f"{code_type:02x}"
        
        if code_type in [0x03, 0x04, 0x06, 0x07]:  # Single address + command
            address = f"{code1:02x}"
            command = f"{code2:02x}"
        elif code_type in [0x05, 0x08]:  # Address MSB, LSB + command
            address = f"{code1:02x}{code2:02x}"
            command = f"{code3:02x}"
        else:
            address = f"{code1:02x}"
            command = f"{code2:02x}_{code3:02x}"
        
        # Notify event entity
        self.notify_entities(address, command, protocol, code_type_hex)


    async def send_ir_code(self, ir_code: str) -> bool:
        """Send IR code via the transmitter."""
        try:
            # Konwersja kodu IR z hex string na bajty
            code_bytes = bytes.fromhex(ir_code)
            
            if len(code_bytes) > 5:
                _LOGGER.error("IR code too long (max 5 bytes): %s", ir_code)
                return False

            # Ramka 0x302: wyślij kod IR
            # Struktura: [0xAA, 0x10, 0x30, 0x02, node, group, byte1, byte2, byte3, byte4, byte5, 0x00, 0x00, 0xFF, 0xA5]
            frame = bytearray([0xAA, 0x10, 0x30, 0x02, self.node, self.group, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0xFF, 0xA5])
            
            # Wstaw kod IR
            for i, byte in enumerate(code_bytes):
                if i < 5:
                    frame[6 + i] = byte
            
            await self.gateway.send(frame)
            _LOGGER.info("IR code sent: %s from device %s", ir_code, self.id)
            return True

        except ValueError:
            _LOGGER.error("Invalid IR code format (must be hex): %s", ir_code)
            return False
        except Exception as e:
            _LOGGER.error("Error sending IR code: %s", e)
            return False

    # ---------------------------------------------------------
    #  COMPLETENESS CHECK
    # ---------------------------------------------------------

    def is_complete(self) -> bool:
        if not super().is_complete():
            return False
        return True

