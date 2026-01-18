import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up HAPCAN sensors from a config entry."""

    data = hass.data[DOMAIN][entry.entry_id]
    devices = data["devices"]
    gateway = data["gateway"]

    # -----------------------------------------------------------------------------------
    # EVENT HANDLERS
    # -----------------------------------------------------------------------------------

    async def _on_register_entities(device):
        _LOGGER.debug("Registering SENSOR platform entities for device %s", device)

        # Pobieramy encje diagnostyczne (np. LastSeenEntity)
        entities = device.entities.get("diagnostic", [])

        if entities:
            _LOGGER.debug(" Entity list:")
            for ent in entities:
                _LOGGER.debug("  %s", ent)

            async_add_entities(entities)
            _LOGGER.debug(" %s sensor entities registered", len(entities))

        else:
            _LOGGER.debug(" No SENSOR entities for this device. Registration skipped.")

    # Podpinamy się pod ten sam dispatcher co switch.py,
    # ale każda platforma dostaje swoje encje.
    async_dispatcher_connect(
        hass,
        f"hapcan_register_entities_{entry.entry_id}",
        _on_register_entities
    )