"""Binary sensor entities for Samsung Washer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import device_info
from .const import DOMAIN
from .coordinator import SamsungWasherCoordinator


@dataclass(frozen=True, kw_only=True)
class WasherBinarySensorDescription(BinarySensorEntityDescription):
    data_key: str = ""
    true_value: Any = "true"


BINARY_SENSOR_DESCRIPTIONS: tuple[WasherBinarySensorDescription, ...] = (
    WasherBinarySensorDescription(
        key="remote_enabled",
        data_key="remote_enabled",
        name="Remote Control",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        true_value="true",
        icon="mdi:remote",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SamsungWasherCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([
        WasherBinarySensor(coordinator, entry, desc)
        for desc in BINARY_SENSOR_DESCRIPTIONS
    ])


class WasherBinarySensor(
    CoordinatorEntity[SamsungWasherCoordinator], BinarySensorEntity
):
    entity_description: WasherBinarySensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SamsungWasherCoordinator,
        entry: ConfigEntry,
        description: WasherBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = device_info(entry)

    @property
    def is_on(self) -> bool | None:
        val = self.coordinator.data.get(self.entity_description.data_key)
        if val is None:
            return None
        return str(val).lower() == str(self.entity_description.true_value).lower()
