"""Samsung Washer custom integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.device_registry import DeviceInfo

from .api import SmartThingsWasherAPI
from .const import (
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    CONF_DEFAULT_DRY,
    CONF_DEFAULT_RINSE,
    CONF_DEFAULT_SPIN,
    CONF_DEFAULT_TEMP,
    CYCLE_ALL_IN_ONE_NAME,
    CYCLE_DRYING_ONLY_NAME,
    CYCLE_QUICK_15_NAME,
    DEFAULT_DRY_LEVEL,
    DEFAULT_RINSE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SPIN,
    DEFAULT_TEMP,
    DOMAIN,
    PLATFORMS,
    VALID_DRY_LEVELS_AIO,
    VALID_DRY_LEVELS_DRY,
    VALID_RINSES,
    VALID_SPINS,
    VALID_TEMPS,
)
from .coordinator import SamsungWasherCoordinator

_LOGGER = logging.getLogger(__name__)

# ── Service schema ────────────────────────────────────────────────────────────

SERVICE_START_CYCLE = "start_cycle"
SERVICE_STOP        = "stop"
SERVICE_PAUSE       = "pause"

_START_SCHEMA = vol.Schema({
    vol.Optional("cycle"):     vol.In([CYCLE_ALL_IN_ONE_NAME, CYCLE_DRYING_ONLY_NAME, CYCLE_QUICK_15_NAME]),
    vol.Optional("temp"):      vol.In(VALID_TEMPS),
    vol.Optional("spin"):      vol.In(VALID_SPINS),
    vol.Optional("rinse"):     vol.In(VALID_RINSES),
    vol.Optional("dry_level"): vol.In(VALID_DRY_LEVELS_AIO),
})

_ENTRY_SCHEMA = vol.Schema({vol.Required("entry_id"): str})


def _get_coordinator(hass: HomeAssistant, entry_id: str) -> SamsungWasherCoordinator:
    return hass.data[DOMAIN][entry_id]["coordinator"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Samsung Washer from a config entry."""
    device_id = entry.data[CONF_DEVICE_ID]
    opts      = entry.options

    implementation = await async_get_config_entry_implementation(hass, entry)
    oauth_session  = OAuth2Session(hass, entry, implementation)

    api = SmartThingsWasherAPI(oauth_session, device_id)

    scan_interval = opts.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator   = SamsungWasherCoordinator(
        hass, api, entry.title, scan_interval=scan_interval
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "api": api,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ── Register services ─────────────────────────────────────────────────────

    async def _handle_start(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id", entry.entry_id)
        coord    = _get_coordinator(hass, entry_id)
        opts     = coord.hass.data[DOMAIN][entry_id]  # noqa: F841 — reserved

        cycle = call.data.get("cycle", coord.selected_cycle)
        temp  = call.data.get("temp",  entry.options.get(CONF_DEFAULT_TEMP, DEFAULT_TEMP))
        spin  = call.data.get("spin",  entry.options.get(CONF_DEFAULT_SPIN, DEFAULT_SPIN))
        rinse = call.data.get("rinse", entry.options.get(CONF_DEFAULT_RINSE, DEFAULT_RINSE))
        dry   = call.data.get("dry_level", entry.options.get(CONF_DEFAULT_DRY, DEFAULT_DRY_LEVEL))

        if cycle == CYCLE_ALL_IN_ONE_NAME:
            await coord.api.start_all_in_one(temp, spin, rinse, dry)
        elif cycle == CYCLE_DRYING_ONLY_NAME:
            await coord.api.start_drying_only(dry if dry in VALID_DRY_LEVELS_DRY else "cupboard")
        elif cycle == CYCLE_QUICK_15_NAME:
            await coord.api.start_quick_15()

        await coordinator.async_request_refresh()

    async def _handle_stop(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id", entry.entry_id)
        await _get_coordinator(hass, entry_id).api.stop()
        await coordinator.async_request_refresh()

    async def _handle_pause(call: ServiceCall) -> None:
        entry_id = call.data.get("entry_id", entry.entry_id)
        await _get_coordinator(hass, entry_id).api.pause()
        await coordinator.async_request_refresh()

    if not hass.services.has_service(DOMAIN, SERVICE_START_CYCLE):
        hass.services.async_register(DOMAIN, SERVICE_START_CYCLE, _handle_start, schema=_START_SCHEMA)
        hass.services.async_register(DOMAIN, SERVICE_STOP,  _handle_stop)
        hass.services.async_register(DOMAIN, SERVICE_PAUSE, _handle_pause)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            for svc in (SERVICE_START_CYCLE, SERVICE_STOP, SERVICE_PAUSE):
                hass.services.async_remove(DOMAIN, svc)
    return unload_ok


def device_info(entry: ConfigEntry) -> DeviceInfo:
    """Shared DeviceInfo used by all entities in this integration."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.data[CONF_DEVICE_ID])},
        name=entry.title,
        manufacturer="Samsung",
        model="WW6600R Washer-Dryer",
    )
