"""Button entities for Samsung Washer (Start / Stop / Pause / Check Status)."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import device_info
from .const import DOMAIN
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
        self.entity_description = description
        self._attr_unique_id   = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = device_info(entry)

    async def async_press(self) -> None:
        api = self._coordinator.api

        if self.entity_description.action == "start":
            # Cycle + settings already sent to machine via selects.
            # Just send the start command.
            await api._start()

        elif self.entity_description.action == "stop":
            await api.stop()

        elif self.entity_description.action == "pause":
            await api.pause()

        elif self.entity_description.action == "check_status":
            # Force-refresh sensors from device.
            pass

        await self._coordinator.async_request_refresh()
