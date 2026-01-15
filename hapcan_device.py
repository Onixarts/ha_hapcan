from .const import HARDWARE_TYPE_TO_STRING_MAP

from datetime import datetime, timezone
from .last_seen_entity import LastSeenSensorEntity
from .bus_voltage_entity import BusVoltageSensorEntity
from .cpu_voltage_entity import CpuVoltageSensorEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect



import logging
_LOGGER = logging.getLogger(__name__)

class HapcanDevice:
    """
    Reprezentuje pojedynczy moduł HAPCAN.
    """

    # Lista urządzeń wspierających ramkę 0x117
    frame0x117Support = [
        [3, 1, 0, 0],  # 8 CHANNEL DIN RAIL BOX BUTTON
        [3, 1, 2, 1],  # 6 CHANNEL BACK BOX TOUCH BUTTON
        [3, 1, 3, 1],  # 14 CHANNEL BACK BOX BUTTON
        [3, 2, 1, 0],  # 5A MONOSTABLE RELAY
        [3, 2, 2, 0],  # 5A BISTABLE RELAY
        [3, 2, 3, 0],  # 16A MONOSTABLE RELAY
        [3, 2, 4, 3],  # 16A BISTABLE RELAY
        [3, 2, 5, 0],  # 6A MONOSTABLE RELAY
        [3, 5, 0, 3],  # INFRARED RECEIVER & TRANSMITTER
        [3, 6, 0, 2],  # DIMMER RC
        [3, 7, 0, 0],  # BLIND CONTROLLER for AC MOTORS
        [3, 8, 0, 0],  # RGB LED CONTROLLER
        [3, 9, 0, 0],  # 10 CHANNEL OPEN COLLECTOR
    ]

    def __init__(self, node, group, gateway):
        self.id = f"{node:03d}_{group:03d}"
        self.node = node
        self.group = group
        self.gateway = gateway
        
        self._desc_chunks = 0
        self.description = ""
        self.serial_number = 0

        self.hardware_type_string = "unknown hardware"
        
        self.hardware_version = 0 # eg. 3
        self.application_type = 0 # eg. 1 - button, 2 -relay
        self.application_type_icon = "fa-microchip"
        self.application_version = 0 # eg. 0 - button 8x din, 3 - 2 - 6 x touch button, 3 - 14 x button with LED
        self.firmware_version = 0 # idk

        self.entities = {}
        self.entities_registered = False

        self._ready_entities = 0

        # DIAGNOSTIC DATA
        self.last_seen = None
        self.bus_voltage = None
        self.cpu_voltage = None

        # DIAGNOSTIC ENTITES
        self._last_seen_entity = None
        self._cpu_voltage_entity = None
        self._bus_voltage_entity = None

        # HAPCAN MESSAGE SUBSCRIPTION 
        self._unsub_10C = async_dispatcher_connect( gateway._hass, "hapcan_frame_10c", self._handle_voltage_frame_10C )


    async def async_will_remove_from_hass(self):
        if self._unsub_10C:
            self._unsub_10C()        

    def cleanup(self):
        if self._unsub_10C:
            self._unsub_10C()
            self._unsub_10C = None
        
    @property
    def application_type_string(self):
        return "base device type"

    @property
    def hardware_type(self):
        return self._hardware_type
    
    @hardware_type.setter
    def hardware_type(self, value):
        self._hardware_type = value
        self.hardware_type_string = HARDWARE_TYPE_TO_STRING_MAP.get(value, "unknown device type (not supported)")

    @property
    def device_info(self):
        return {
            "identifiers": {("hapcan", f"{self.id}")},
            "manufacturer": "HAPCAN"
        }


    def create_entities(self):
        _LOGGER.debug("HAPCAN: Device %s is creating base entities", self)
        self.entities = {
            "switch": [],
            "diagnostic": []
        }

        # create common base entities

        self._last_seen_entity = LastSeenSensorEntity(self)
        self._bus_voltage_entity = BusVoltageSensorEntity(self)
        self._cpu_voltage_entity = CpuVoltageSensorEntity(self)
        
        self.entities["diagnostic"].append(self._last_seen_entity)
        self.entities["diagnostic"].append(self._bus_voltage_entity)
        self.entities["diagnostic"].append(self._cpu_voltage_entity)

        # create device specific entities
        self._create_entities()

        
    def _create_entities(self):
        pass

    async def entity_ready(self, entity):
        self._ready_entities += 1
        all_entities_count = sum(len(lst) for lst in self.entities.values())
        _LOGGER.debug("Entity #%s/%s ready for device %s", self._ready_entities, all_entities_count, self)

        if self._ready_entities == all_entities_count:
            _LOGGER.debug(
                "All %s entities ready. Requesting status for device %s",
                all_entities_count, self,
            )
            await self.request_status()

    # ---------------------------------------------------------
    #  Interpretacja ramek informacyjnych
    # ---------------------------------------------------------

    def _handle_voltage_frame_10C(self, msg):
        
        node = msg.node
        group = msg.group
        frame = msg.frame

        if msg.node != self.node or msg.group != self.group:
            return

        _LOGGER.debug("Processing 0x10C frame with voltage response for device %s", self)

        self.bus_voltage = ( frame[5]*256 + frame[6] ) * 30.5 / 65472
        self.cpu_voltage = ( frame[7]*256 + frame[8] ) * 5 / 65472

        if self._bus_voltage_entity:
            self._bus_voltage_entity.device_updated()

        if self._cpu_voltage_entity:
            self._cpu_voltage_entity.device_updated()


    @classmethod
    def from_existing(cls, old):
        new = cls(old.node, old.group, old.gateway)
        old._copy_base_fields_to(new)
        return new

    def _copy_base_fields_to(self, other):
        other.serial_number = self.serial_number
        other.hardware_type = self.hardware_type
        other.hardware_version = self.hardware_version
        other.application_type = self.application_type
        other.application_version = self.application_version
        other.firmware_version = self.firmware_version
        other.entities_registered = self.entities_registered
        other.last_seen = self.last_seen


    async def request_status(self):
        """Send 0x109 status request to the module."""

        frame = bytearray([ 0xAA, 0x10, 0x90, 0xF0, 0xF0, 0xFF, 0xFF, self.node, self.group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5 ])
        await self.gateway.send(frame)


    async def request_voltage(self):
        _LOGGER.debug("Requesting voltage for device %s", self)
        frame = bytearray([ 0xAA, 0x10, 0xC0, 0xF0, 0xF0, 0xFF, 0xFF, self.node, self.group, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xA5 ])
        await self.gateway.send(frame)


    def supportsFrame0x117(self) -> bool:
        """Sprawdza, czy urządzenie wspiera ramkę 0x117 - pobieranie nazwy encji bez restartu urządzenia"""
        for minimal in self.frame0x117Support:
            if (
                self.hardware_version == minimal[0]
                and self.application_type == minimal[1]
                and self.application_version == minimal[2]
                and self.firmware_version >= minimal[3]
            ):
                return True
        return False

    def is_complete(self) -> bool:
        return (
            self.serial_number is not None and
            self.hardware_type is not None and
            self.application_type is not None and
            self.application_version is not None and
            self.firmware_version is not None and
            self._desc_chunks == 1
        )

    def update_last_seen(self):
        self.last_seen = datetime.now(timezone.utc)
        
        for entity in self.entities.get("diagnostic", []):
            entity.device_updated()



    def __repr__(self):
        desc = f' "{self.description}"' if self.description else ""
        return (
            f"<{self.__class__.__name__} {self.hardware_version}.{self.application_type}.{self.application_version}.{self.firmware_version} "
            f"{self.hardware_type_string} {self.application_type_string} ({self.node},{self.group}){desc}, "
            f"entities={sum(len(lst) for lst in self.entities.values())}>"
        )
