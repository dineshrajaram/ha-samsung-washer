"""Cycle selector entity for Samsung Washer."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import device_info
from .const import CYCLE_ALL_IN_ONE_NAME, CYCLE_OPTIONS, DOMAIN
from .coordinator import SamsungWasherCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SamsungWasherCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([WasherCycleSelect(coordinator, entry)])


class WasherCycleSelect(RestoreEntity, SelectEntity):
    """
    Lets the user pick which cycle to start next.

    State is local (not read from the device) and is restored across HA restarts.
    The Start button (button.py) and samsung_washer.start_cycle service read this value.
    """

    _attr_has_entity_name = True
    _attr_name = "Cycle"
    _attr_icon = "mdi:washing-machine"
    _attr_options = CYCLE_OPTIONS

    def __init__(
        self,
        coordinator: SamsungWasherCoordinator,
        entry: ConfigEntry,
    ) -> None:
        self._coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}_cycle_select"
        self._attr_device_info = device_info(entry)
        self._attr_current_option = CYCLE_ALL_IN_ONE_NAME

    async def async_added_to_hass(self) -> None:
        """Restore last selected cycle after HA restart."""
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) and last.state in CYCLE_OPTIONS:
            self._attr_current_option = last.state
            self._coordinator.selected_cycle = last.state

    async def async_select_option(self, option: str) -> None:
        """Called when the user picks a cycle in the UI."""
        self._attr_current_option = option
        self._coordinator.selected_cycle = option
        self.async_write_ha_state()
