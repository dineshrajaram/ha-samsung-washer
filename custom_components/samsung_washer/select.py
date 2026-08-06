"""Select entities for Samsung Washer.

Three selects — all send to the machine immediately on change:
  - Cycle            → setWasherCycle  → coordinator refresh → sensors update
  - Softener Amount  → setDispenseAmount
  - Detergent Amount → setDispenseAmount

Temp / spin / rinse / dry are read-only sensors (machine sets them from the cycle).
"""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import cycles as cycles_mod
from . import device_info
from .const import (
    DEFAULT_DETERGENT_AMOUNT,
    DEFAULT_SOFTENER_AMOUNT,
    DOMAIN,
    VALID_DISPENSE_AMOUNTS,
)
from .coordinator import SamsungWasherCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SamsungWasherCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([
        WasherCycleSelect(coordinator, entry),
        WasherDispenseSelect(
            coordinator, entry,
            key="softener_amount",
            name="Softener Amount",
            icon="mdi:bottle-tonic",
            default=DEFAULT_SOFTENER_AMOUNT,
            status_key="softener_amount",
            api_method="set_softener_amount",
        ),
        WasherDispenseSelect(
            coordinator, entry,
            key="detergent_amount",
            name="Detergent Amount",
            icon="mdi:bottle-tonic-outline",
            default=DEFAULT_DETERGENT_AMOUNT,
            status_key="detergent_amount",
            api_method="set_detergent_amount",
        ),
    ])


# ── Cycle select ──────────────────────────────────────────────────────────────

class WasherCycleSelect(
    CoordinatorEntity[SamsungWasherCoordinator], RestoreEntity, SelectEntity
):
    """
    Sends setWasherCycle immediately on selection.
    The machine updates its defaults; coordinator refresh populates all sensors.
    """

    _attr_has_entity_name = True
    _attr_name = "Cycle"
    _attr_icon = "mdi:washing-machine"

    def __init__(self, coordinator: SamsungWasherCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id   = f"{entry.entry_id}_cycle"
        self._attr_device_info = device_info(entry)
        self._update_options()
        if self._attr_options:
            first = self._attr_options[0]
            self._attr_current_option = first
            coordinator.selected_cycle = first

    def _update_options(self) -> None:
        self._attr_options = [c["name"] for c in self.coordinator.named_cycles]

    def _handle_coordinator_update(self) -> None:
        self._update_options()
        if self._attr_current_option not in (self._attr_options or []):
            if self._attr_options:
                self._attr_current_option = self._attr_options[0]
                self.coordinator.selected_cycle = self._attr_options[0]
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) and last.state in (self._attr_options or []):
            self._attr_current_option = last.state
            self.coordinator.selected_cycle = last.state

    async def async_select_option(self, option: str) -> None:
        """Send cycle to machine, then refresh so sensors show machine defaults."""
        self._attr_current_option = option
        self.coordinator.selected_cycle = option
        self.async_write_ha_state()

        cycle = cycles_mod.by_name(option, self.coordinator.hass.data
                                   .get(DOMAIN, {})
                                   .get(self._attr_unique_id.split("_")[0], {})
                                   .get("entry", {}).options
                                   if False else None)
        # Simpler: look up from coordinator.named_cycles directly
        entry = next(
            (c for c in self.coordinator.named_cycles if c["name"] == option), None
        )
        if entry:
            await self.coordinator.api.set_cycle(entry["code"])
            await self.coordinator.async_request_refresh()


# ── Dispense selects (softener / detergent) ───────────────────────────────────

class WasherDispenseSelect(
    CoordinatorEntity[SamsungWasherCoordinator], RestoreEntity, SelectEntity
):
    """
    Amount selector for auto-dispense (softener or detergent).
    Sends setDispenseAmount to the machine immediately on change.
    Initialised from current device status.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SamsungWasherCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
        default: str,
        status_key: str,
        api_method: str,
    ) -> None:
        super().__init__(coordinator)
        self._status_key  = status_key
        self._api_method  = api_method
        self._attr_unique_id      = f"{entry.entry_id}_{key}"
        self._attr_name           = name
        self._attr_icon           = icon
        self._attr_options        = VALID_DISPENSE_AMOUNTS
        self._attr_current_option = default
        self._attr_device_info    = device_info(entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) and last.state in VALID_DISPENSE_AMOUNTS:
            self._attr_current_option = last.state
            return
        self._sync_from_device()

    def _sync_from_device(self) -> None:
        if self.coordinator.data:
            val = self.coordinator.data.get(self._status_key)
            if val and val in VALID_DISPENSE_AMOUNTS:
                self._attr_current_option = val

    def _handle_coordinator_update(self) -> None:
        self._sync_from_device()
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Send dispense amount to machine immediately."""
        self._attr_current_option = option
        self.async_write_ha_state()
        await getattr(self.coordinator.api, self._api_method)(option)
        await self.coordinator.async_request_refresh()
