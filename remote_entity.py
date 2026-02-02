import logging

from homeassistant.components.remote import RemoteEntity as HA_RemoteEntity
from .hapcan_entity import HapcanEntity

_LOGGER = logging.getLogger(__name__)


class RemoteEntity(HapcanEntity, HA_RemoteEntity):
    """HAPCAN IR transmitter represented as a remote entity."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:remote"
    _attr_name = "IR Transmitter"

    def __init__(self, device):
        HapcanEntity.__init__(self, device)
        HA_RemoteEntity.__init__(self)

        self._attr_unique_id = f"{device.id}_ir_transmitter"

    def __repr__(self):
        return (
            f"<RemoteEntity unique_id={self._attr_unique_id!r} "
            f"name={self._attr_name!r} "
            f"device={self._device.id!r}>"
        )

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return True

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the device on. Not supported for IR transmitter."""
        _LOGGER.debug("IR transmitter is always active")

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the device off. Not supported for IR transmitter."""
        _LOGGER.debug("IR transmitter is always active")

    # ---------------------------------------------------------------------------
    # SEND COMMAND
    # ---------------------------------------------------------------------------

    async def async_send_command(self, command: list[str], **kwargs) -> None:
        """Send command(s) via IR transmitter.
        
        Args:
            command: List of IR codes in hex format (e.g., ["aabbccdd", "11223344"])
        """
        try:
            if not command:
                _LOGGER.warning("No commands provided to send")
                return

            for ir_code in command:
                # Validate hex format
                try:
                    bytes.fromhex(ir_code)
                except ValueError:
                    _LOGGER.error("Invalid hex format for IR code: %s", ir_code)
                    continue

                # Send the code
                success = await self._device.send_ir_code(ir_code)
                if not success:
                    _LOGGER.error("Failed to send IR code: %s", ir_code)

        except Exception as e:
            _LOGGER.error("Error in async_send_command: %s", e)
