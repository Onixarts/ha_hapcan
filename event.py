import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers import device_registry as dr

from .const import (
    CONF_ADDRESS,
    CONF_BUTTONS,
    CONF_CODE_TYPE,
    CONF_MODULE_ID,
    DOMAIN,
    SUBENTRY_TYPE_IR_REMOTE,
    get_ir_device_by_module_id,
)
from .ir_device import IRDevice
from .ir_remote_entity import IRRemoteEventEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry( hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    """Set up HAPCAN event entities (physical buttons) from a config entry."""

    data = hass.data[DOMAIN][entry.entry_id]
    devices = data["devices"]
    data["async_add_ir_remote_entities"] = async_add_entities

    # ---------------------------------------------------------------------------
    # EVENT HANDLER
    # ---------------------------------------------------------------------------

    async def _on_register_entities(device):
        _LOGGER.debug("Registering EVENT platform entities for device %s", device)

        entities = device.entities.get("event", [])
        to_register = [ent for ent in entities if not getattr(ent, "registered", False)]
        if to_register:
            _LOGGER.debug("Registering %d EVENT entities for device %s", len(to_register), device)
            async_add_entities(to_register)

        if isinstance(device, IRDevice):
            await async_sync_ir_remotes(hass, entry, device=device)


    entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"hapcan_register_entities_{entry.entry_id}", _on_register_entities
        )
    )

    await async_sync_ir_remotes(hass, entry)


async def async_sync_ir_remotes(hass, entry, *, device=None):
    """Create, update, and remove event entities for configured IR remotes."""
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    devices = data.get("devices", {})
    entities = data.setdefault("ir_remotes", {})
    add_entities = data.get("async_add_ir_remote_entities")
    subentries = getattr(entry, "subentries", {})
    desired_ids = set()

    for subentry in subentries.values():
        if getattr(subentry, "subentry_type", None) != SUBENTRY_TYPE_IR_REMOTE:
            continue

        subentry_id = subentry.subentry_id
        desired_ids.add(subentry_id)
        subentry_data = subentry.data
        module_id = subentry_data.get(CONF_MODULE_ID)
        remote_device = get_ir_device_by_module_id(devices, module_id)
        if remote_device is None or not isinstance(remote_device, IRDevice):
            continue
        module_id = remote_device.id
        if device is not None and remote_device is not device:
            continue

        parent_device = dr.async_get(hass).async_get_device_by_identifier(
            (DOMAIN, remote_device.id), entry.entry_id
        )
        if parent_device is None:
            _LOGGER.warning(
                "Cannot register IR remote %s: receiver device %s is not in the device registry",
                subentry.title,
                remote_device.id,
            )
            continue

        entity = entities.get(subentry_id)
        if entity is not None:
            entity.update_title(subentry.title)
            entity.update_buttons(subentry_data.get(CONF_BUTTONS, {}))
            continue

        entity = IRRemoteEventEntity(
            remote_device,
            module_id=module_id,
            code_type=subentry_data[CONF_CODE_TYPE],
            address=subentry_data[CONF_ADDRESS],
            title=subentry.title,
            buttons=subentry_data.get(CONF_BUTTONS, {}),
            via_device_id=parent_device.id,
        )
        entities[subentry_id] = entity
        if add_entities is not None:
            add_entities([entity], config_subentry_id=subentry_id)

    for subentry_id, entity in list(entities.items()):
        if subentry_id in desired_ids:
            continue
        entities.pop(subentry_id)
        await entity.async_remove(force_remove=True)
