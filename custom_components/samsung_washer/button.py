"""Button entities for Samsung Washer (Start / Stop / Pause)."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import device_info
from .const import (
    CONF_DEFAULT_DRY,
    CONF_DEFAULT_RINSE,
    CONF_DEFAULT_SPIN,
    CONF_DEFAULT_TEMP,
    CYCLE_ALL_IN_ONE_NAME,
    CYCLE_DRYING_ONLY_NAME,
    CYCLE_QUICK_15_NAME,
    DEFAULT_DRY_LEVEL,
    DEFAULT_RINSE,
    DEFAULT_SPIN,
    DEFAULT_TEMP,
    DOMAIN,
    VALID_DRY_LEVELS_DRY,
)
from .coordinator import SamsungWasherCoordinator


@dataclass(frozen=True, kw_only=True)
class WasherButtonDescription(ButtonEntityDescription):
    action: str = ""


BUTTON_DESCRIPTIONS: tuple[WasherButtonDescription, ...] = (
    WasherButtonDescription(
        key="start",
        name="Start",
        icon="mdi:play-circle-outline",
        action="start",
    ),
    WasherButtonDescription(
        key="stop",
        name="Stop",
        icon="mdi:stop-circle-outline",
        action="stop",
    ),
    WasherButtonDescription(
        key="pause",
        name="Pause",
        icon="mdi:pause-circle-outline",
        action="pause",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SamsungWasherCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([
        WasherButton(coordinator, entry, desc) for desc in BUTTON_DESCRIPTIONS
    ])


class WasherButton(ButtonEntity):
    """A button that sends a command to the washer."""

    entity_description: WasherButtonDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SamsungWasherCoordinator,
        entry: ConfigEntry,
        description: WasherButtonDescription,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = device_info(entry)

    async def async_press(self) -> None:
        """Handle button press."""
        api  = self._coordinator.api
        opts = self._entry.options

        if self.entity_description.action == "start":
            cycle = self._coordinator.selected_cycle
            temp  = opts.get(CONF_DEFAULT_TEMP, DEFAULT_TEMP)
            spin  = opts.get(CONF_DEFAULT_SPIN, DEFAULT_SPIN)
            rinse = opts.get(CONF_DEFAULT_RINSE, DEFAULT_RINSE)
            dry   = opts.get(CONF_DEFAULT_DRY, DEFAULT_DRY_LEVEL)

            if cycle == CYCLE_ALL_IN_ONE_NAME:
                await api.start_all_in_one(temp, spin, rinse, dry)
            elif cycle == CYCLE_DRYING_ONLY_NAME:
                await api.start_drying_only(dry if dry in VALID_DRY_LEVELS_DRY else "cupboard")
            elif cycle == CYCLE_QUICK_15_NAME:
                await api.start_quick_15()

        elif self.entity_description.action == "stop":
            await api.stop()

        elif self.entity_description.action == "pause":
            await api.pause()

        await self._coordinator.async_request_refresh()
