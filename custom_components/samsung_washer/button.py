"""Button entities for Samsung Washer (Start / Stop / Pause / Check Status)."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import cycles as cycles_mod
from . import device_info
from .const import DOMAIN, VALID_DRY_LEVELS_DRY
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
    WasherButtonDescription(
        key="check_status",
        name="Check Status",
        icon="mdi:refresh-circle",
        action="check_status",
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
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SamsungWasherCoordinator,
        entry: ConfigEntry,
        description: WasherButtonDescription,
    ) -> None:
        self._coordinator = coordinator
        self._entry       = entry
        self.entity_description = description
        self._attr_unique_id   = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = device_info(entry)

    def _resolve_cycle(self) -> tuple[str | None, str | None]:
        """Return (cycle_code, cycle_type) for the currently selected cycle name."""
        name  = self._coordinator.selected_cycle
        entry = cycles_mod.by_name(name, self._entry.options)
        if entry:
            return entry["code"], entry["cycle_type"]
        return None, None

    async def async_press(self) -> None:
        api   = self._coordinator.api
        coord = self._coordinator

        if self.entity_description.action == "start":
            code, cycle_type = self._resolve_cycle()
            if code is None:
                return

            if cycle_type == "dryingOnly":
                dry = coord.selected_dry_level
                if dry not in VALID_DRY_LEVELS_DRY:
                    dry = "cupboard"
                await api.start_drying_only(dry_level=dry)

            elif cycle_type in ("allInOne", "washingOnly"):
                await api.start_regular_wash(
                    water_temp=coord.selected_temp,
                    spin_level=coord.selected_spin,
                    rinse_cycles=coord.selected_rinse,
                    dry_level=coord.selected_dry_level,
                    softener_amount=coord.selected_softener_amount,
                    detergent_amount=coord.selected_detergent_amount,
                )
            else:
                # Quick wash / other — use hca.washerMode
                await api.start_quick_15()

        elif self.entity_description.action == "stop":
            await api.stop()

        elif self.entity_description.action == "pause":
            await api.pause()

        elif self.entity_description.action == "check_status":
            code, _ = self._resolve_cycle()
            if code:
                await api.set_cycle(code)

        await self._coordinator.async_request_refresh()
