import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry( hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up HAPCAN event entities (physical buttons) from a config entry."""

    data = hass.data[DOMAIN][entry.entry_id]
    devices = data["devices"]
    gateway = data["gateway"]

    # ---------------------------------------------------------------------------
    # EVENT HANDLER
    # ---------------------------------------------------------------------------

    async def _on_register_entities(device):
        _LOGGER.debug("Registering EVENT platform entities for device %s", device)

        entities = device.entities.get("event", [])

        if not entities:
            _LOGGER.debug(" No EVENT entities for this device. Registration skipped.")
            return

        to_register = [ ent for ent in entities if not getattr(ent, "_registered", False) ]

        if not to_register:
            _LOGGER.debug( " All EVENT entities already registered for device %s. Skipping.", device)
            return

        _LOGGER.debug(" Event entities to register:")
        for ent in to_register:
            _LOGGER.debug("  %s", ent)

        async_add_entities(to_register)


    async_dispatcher_connect( hass, f"hapcan_register_entities_{entry.entry_id}", _on_register_entities )