import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers import discovery
from homeassistant.helpers import device_registry as dr

from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from homeassistant.config_entries import ConfigEntry


from .gateway import HapcanGateway
from .const import DOMAIN, DEFAULT_DIAGNOSTIC_SCAN_INTERVAL_MINUTES

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up HAPCAN from a config entry."""

    host = entry.data["host"]
    port = entry.data["port"]
    diagnostic_scan_interval_minutes = entry.options.get(
        "diagnostic_scan_interval_minutes",
        entry.data.get("diagnostic_scan_interval_minutes", DEFAULT_DIAGNOSTIC_SCAN_INTERVAL_MINUTES)
    )
    
    gateway = HapcanGateway(hass, entry.entry_id, options={
            "host": host,
            "port": port,
            "diagnostic_scan_interval_minutes": diagnostic_scan_interval_minutes
        })

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN]["gateway"] = gateway
    hass.data[DOMAIN][entry.entry_id] = {
        "gateway": gateway,
        "devices": {},
    }
    

    #-----------------------------------------------------------------------------------
    # EVENT HANDLERS
    #-----------------------------------------------------------------------------------

    async def _on_device_ready(device):
        _LOGGER.debug("Registering device %s", device )
        device_registry = dr.async_get(hass)

        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device.id)},
            manufacturer="HAPCAN",
            name=device.description or f"HAPCAN {device.application_type_string} ({device.node},{device.group})",
            model=f"{device.hardware_type_string} - {device.application_type_string}",
            serial_number = device.serial_number,
            hw_version=f"{device.hardware_version}.{device.application_type}.{device.application_version}.X",
            sw_version=f"{device.hardware_version}.{device.application_type}.{device.application_version}.{device.firmware_version}",
        )

        # SAFE CREATE ENTITIES AND NOTIFY PLATFORMS

        device.create_entities()
        async_dispatcher_send( hass, f"hapcan_register_entities_{entry.entry_id}", device )


    async_dispatcher_connect( hass, f"hapcan_device_ready_{entry.entry_id}", _on_device_ready)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await gateway.connect()

    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload HAPCAN config entry."""

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
