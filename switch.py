import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, EVENT_DEVICE_UPDATED

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry( hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up HAPCAN relay switches from a config entry."""

    data = hass.data[DOMAIN][entry.entry_id]
    devices = data["devices"]
    gateway = data["gateway"]


    #-----------------------------------------------------------------------------------
    # EVENT HANDLERS
    #-----------------------------------------------------------------------------------

    async def _on_register_entities(device):
        _LOGGER.debug("Registering SWITCH platform entities for device %s", device)
        
        entities = device.entities.get("switch", [])
        if entities:

            _LOGGER.debug(" Entity list:")
            for ent in entities:
                _LOGGER.debug("  %s", ent)
            
            async_add_entities(entities)
            _LOGGER.debug(" %s entities registered.", len(entities))
            device.entities_registered = True
                
        else:
            _LOGGER.debug(" No entities of platform SWITCH. Etity registration skipped.")


    async_dispatcher_connect(hass, f"hapcan_register_entities_{entry.entry_id}", _on_register_entities )