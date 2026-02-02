import logging

from homeassistant.components.remote import RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up HAPCAN remote entities from a config entry."""

    data = hass.data[DOMAIN][entry.entry_id]
    devices = data["devices"]
    gateway = data["gateway"]

    # -----------------------------------------------------------------------------------
    # EVENT HANDLERS
    # -----------------------------------------------------------------------------------

    async def _on_register_entities(device):
        _LOGGER.debug("Registering REMOTE platform entities for device %s", device)

        entities = device.entities.get("remote", [])

        if entities:
            async_add_entities(entities)
            _LOGGER.debug("Added %d remote entities", len(entities))

    async_dispatcher_connect(hass, f"hapcan_register_entities_{entry.entry_id}", _on_register_entities)

    # Process already registered devices
    for device in devices.values():
        await _on_register_entities(device)
