"""Select entities for Samsung Washer — cycle (sent immediately) + wash parameters."""
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
    DEFAULT_DRY_LEVEL,
    DEFAULT_RINSE,
    DEFAULT_SOFTENER_AMOUNT,
    DEFAULT_SPIN,
    DEFAULT_TEMP,
    DOMAIN,
    VALID_DISPENSE_AMOUNTS,
    VALID_DRY_LEVELS_AIO,
    VALID_RINSES,
    VALID_SPINS,
    VALID_TEMPS,
)
from .coordinator import SamsungWasherCoordinator


@dataclass(frozen=True)
class WasherSelectDescription:
    key:        str
    name:       str
    icon:       str
    options:    list[str]
    default:    str
    coord_attr: str
    status_key: str | None = None


PARAM_DESCRIPTIONS: tuple[WasherSelectDescription, ...] = (
    WasherSelectDescription(
        key="dry_level",       name="Dry Level",
        icon="mdi:air-humidifier",
        options=VALID_DRY_LEVELS_AIO, default=DEFAULT_DRY_LEVEL,
        coord_attr="selected_dry_level",  status_key="dry_level",
    ),
    WasherSelectDescription(
        key="water_temp",      name="Water Temperature",
        icon="mdi:thermometer-water",
        options=VALID_TEMPS,  default=DEFAULT_TEMP,
        coord_attr="selected_temp",       status_key="water_temp",
    ),
    WasherSelectDescription(
        key="spin_speed",      name="Spin Speed",
        icon="mdi:fan",
        options=VALID_SPINS,  default=DEFAULT_SPIN,
        coord_attr="selected_spin",       status_key="spin_level",
    ),
    WasherSelectDescription(
        key="rinse_cycles",    name="Rinse Cycles",
        icon="mdi:water-sync",
        options=VALID_RINSES, default=DEFAULT_RINSE,
        coord_attr="selected_rinse",      status_key="rinse_cycles",
    ),
    WasherSelectDescription(
        key="softener_amount", name="Softener Amount",
        icon="mdi:bottle-tonic",
        options=VALID_DISPENSE_AMOUNTS, default=DEFAULT_SOFTENER_AMOUNT,
        coord_attr="selected_softener_amount", status_key="softener_amount",
    ),
    WasherSelectDescription(
        key="detergent_amount", name="Detergent Amount",
        icon="mdi:bottle-tonic-outline",
        options=VALID_DISPENSE_AMOUNTS, default=DEFAULT_DETERGENT_AMOUNT,
        coord_attr="selected_detergent_amount", status_key="detergent_amount",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SamsungWasherCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([
        WasherCycleSelect(coordinator, entry),
        *[WasherParamSelect(coordinator, entry, desc) for desc in PARAM_DESCRIPTIONS],
    ])


# ── Cycle select ──────────────────────────────────────────────────────────────

class WasherCycleSelect(
    CoordinatorEntity[SamsungWasherCoordinator], RestoreEntity, SelectEntity
):
    """
    Cycle selector driven by named_cycles.json (+ HA option overrides).
    Options list is dynamic — rebuilt whenever the coordinator updates.
    Selecting a cycle stores intent locally; press Check Status to send to machine.
    """

    _attr_has_entity_name = True
    _attr_name  = "Cycle"
    _attr_icon  = "mdi:washing-machine"

    def __init__(self, coordinator: SamsungWasherCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id   = f"{entry.entry_id}_cycle"
        self._attr_device_info = device_info(entry)
        self._update_options()
        # Set default to first available cycle
        if self._attr_options:
            self._attr_current_option = self._attr_options[0]
            self.coordinator.selected_cycle = self._attr_options[0]

    def _update_options(self) -> None:
        self._attr_options = [c["name"] for c in self.coordinator.named_cycles]

    def _handle_coordinator_update(self) -> None:
        # Rebuild options in case cycle names were renamed via options flow
        old_options = list(self._attr_options or [])
        self._update_options()
        # If current selection no longer exists, fall back to first option
        if self._attr_current_option not in (self._attr_options or []):
            if self._attr_options:
                self._attr_current_option = self._attr_options[0]
                self.coordinator.selected_cycle = self._attr_options[0]
        elif old_options != self._attr_options:
            pass  # options changed (rename) but selection still valid
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) and last.state in (self._attr_options or []):
            self._attr_current_option = last.state
            self.coordinator.selected_cycle = last.state

    async def async_select_option(self, option: str) -> None:
        """Store intent locally. Press Check Status to send to machine."""
        self._attr_current_option = option
        self.coordinator.selected_cycle = option
        self.async_write_ha_state()


# ── Parameter selects ─────────────────────────────────────────────────────────

class WasherParamSelect(
    CoordinatorEntity[SamsungWasherCoordinator], RestoreEntity, SelectEntity
):
    """
    Stores user intent for one wash parameter.
    Auto-syncs from device status when the machine's active cycle changes.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SamsungWasherCoordinator,
        entry: ConfigEntry,
        description: WasherSelectDescription,
    ) -> None:
        super().__init__(coordinator)
        self._desc = description
        self._attr_unique_id      = f"{entry.entry_id}_{description.key}"
        self._attr_name           = description.name
        self._attr_icon           = description.icon
        self._attr_options        = description.options
        self._attr_current_option = description.default
        self._attr_device_info    = device_info(entry)
        self._last_seen_cycle: str | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) and last.state in self._desc.options:
            self._attr_current_option = last.state
            setattr(self.coordinator, self._desc.coord_attr, last.state)
            return
        self._sync_from_device()

    def _sync_from_device(self) -> None:
        if not self._desc.status_key or not self.coordinator.data:
            return
        val = self.coordinator.data.get(self._desc.status_key)
        if val and val in self._desc.options:
            self._attr_current_option = val
            setattr(self.coordinator, self._desc.coord_attr, val)

    def _handle_coordinator_update(self) -> None:
        if self.coordinator.data:
            cycle = self.coordinator.data.get("current_cycle")
            if cycle != self._last_seen_cycle:
                self._last_seen_cycle = cycle
                self._sync_from_device()
        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        self._attr_current_option = option
        setattr(self.coordinator, self._desc.coord_attr, option)
        self.async_write_ha_state()
