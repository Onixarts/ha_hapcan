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

        entities = device.entities.get("sensor", []) + device.entities.get("diagnostic", [])

        if entities:

            to_register = [ent for ent in entities if not getattr(ent, "registered", False)]
            if not to_register:
                _LOGGER.debug(" all SENSOR entities already registered for device. Skipping.")
                return

            _LOGGER.debug(" Entity list:")
            for ent in to_register:
                _LOGGER.debug("  %s", ent)

            async_add_entities(to_register)

        else:
            _LOGGER.debug(" No SENSOR entities for this device. Registration skipped.")


    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"hapcan_register_entities_{entry.entry_id}", _on_register_entities
        )
    )