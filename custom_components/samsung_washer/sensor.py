"""Sensor entities for Samsung Washer."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import device_info
from .const import DOMAIN
from .coordinator import SamsungWasherCoordinator


@dataclass(frozen=True, kw_only=True)
class WasherSensorDescription(SensorEntityDescription):
    data_key: str = ""


# ── Sensor definitions ────────────────────────────────────────────────────────

SENSOR_DESCRIPTIONS: tuple[WasherSensorDescription, ...] = (
    WasherSensorDescription(
        key="machine_state",
        data_key="machine_state",
        name="Machine State",
        icon="mdi:washing-machine",
    ),
    WasherSensorDescription(
        key="job_state",
        data_key="job_state",
        name="Job State",
        icon="mdi:washing-machine",
    ),
    WasherSensorDescription(
        key="progress",
        data_key="progress",
        name="Progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:progress-check",
    ),
    WasherSensorDescription(
        key="remaining_time",
        data_key="remaining_time",
        name="Remaining Time",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-outline",
    ),
    WasherSensorDescription(
        key="remaining_time_str",
        data_key="remaining_time_str",
        name="Remaining Time (HH:MM)",
        icon="mdi:timer-outline",
    ),
    WasherSensorDescription(
        key="current_cycle",
        data_key="current_cycle",
        name="Current Cycle",
        icon="mdi:refresh-circle",
    ),
    WasherSensorDescription(
        key="cycle_type",
        data_key="cycle_type",
        name="Cycle Type",
        icon="mdi:format-list-bulleted-type",
    ),
    WasherSensorDescription(
        key="water_temp",
        data_key="water_temp",
        name="Water Temperature",
        icon="mdi:thermometer-water",
    ),
    WasherSensorDescription(
        key="spin_level",
        data_key="spin_level",
        name="Spin Speed",
        icon="mdi:fan",
    ),
    WasherSensorDescription(
        key="rinse_cycles",
        data_key="rinse_cycles",
        name="Rinse Cycles",
        icon="mdi:water-sync",
    ),
    WasherSensorDescription(
        key="dry_level",
        data_key="dry_level",
        name="Dry Level",
        icon="mdi:air-humidifier",
    ),
)


# ── Setup ─────────────────────────────────────────────────────────────────────

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SamsungWasherCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([
        WasherSensor(coordinator, entry, desc) for desc in SENSOR_DESCRIPTIONS
    ])


# ── Entity ────────────────────────────────────────────────────────────────────

class WasherSensor(CoordinatorEntity[SamsungWasherCoordinator], SensorEntity):
    """A sensor that reads from the coordinator's parsed data."""

    entity_description: WasherSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SamsungWasherCoordinator,
        entry: ConfigEntry,
        description: WasherSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = device_info(entry)

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get(self.entity_description.data_key)
