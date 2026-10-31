DOMAIN = "hapcan"
DEFAULT_DIAGNOSTIC_SCAN_INTERVAL_MINUTES = 60
DEFAULT_GROUP_START = 1
DEFAULT_GROUP_END = 10

try:
    from homeassistant.components.event import ButtonEventType
except ImportError:
    class ButtonEventType:
        PRESS_START = "press_start"
        PRESS_END = "press_end"
        LONG_PRESS_START = "long_press_start"
        LONG_PRESS_END = "long_press_end"


BUTTON_EVENT_TYPES = [
    ButtonEventType.PRESS_START,
    ButtonEventType.PRESS_END,
    ButtonEventType.LONG_PRESS_START,
    ButtonEventType.LONG_PRESS_END,
    "held_4s",
    "open",
    "closed",
]

BUTTON_STATE_TO_EVENTS = {
    0x00: (("open", {}),),
    0x01: (),
    0xFF: ((ButtonEventType.PRESS_START, {}), ("closed", {})),
    0xFC: ((ButtonEventType.PRESS_END, {}),),
    0xFE: ((ButtonEventType.LONG_PRESS_START, {}),),
    0xFB: ((ButtonEventType.LONG_PRESS_END, {}),),
    0xFD: (("held_4s", {}),),
    0xFA: ((ButtonEventType.LONG_PRESS_END, {"held_4s": True}),),
}

EVENT_DEVICE_FOUND = "hapcan.device_found"
EVENT_DEVICE_UPDATED = "hapcan.device_updated"
EVENT_DEVICE_READY = "hapcan.device_ready"


HARDWARE_TYPE_UNIV1 = 0x1000
HARDWARE_TYPE_UNIV3 = 0x3000
HARDWARE_TYPE_HAPCANUINO = 0x4F41

HARDWARE_TYPE_TO_STRING_MAP = {
    HARDWARE_TYPE_UNIV1: "UNIV 1",
    HARDWARE_TYPE_UNIV3: "UNIV 3",
    HARDWARE_TYPE_HAPCANUINO: "HAPCANUINO"
}

APPLICATION_TYPE_BUTTON = 0x01
APPLICATION_TYPE_RELAY = 0x02
APPLICATION_TYPE_IR_TRANSMITTER = 0x05
APPLICATION_TYPE_DIMMER = 0x06
APPLICATION_TYPE_BLIND_CONTROLLER = 0x07
APPLICATION_TYPE_LED_CONTROLLER = 0x08
APPLICATION_TYPE_OPEN_COLLECTOR_OUTPUT = 0x09


class HapcanEvent:
    IR_CODE_RECEIVED = "hapcan.ir_code_received"
