"""DataUpdateCoordinator for Samsung Washer."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CannotConnect, SmartThingsWasherAPI
from .const import (
    CYCLE_REGULAR_WASH_NAME,
    DEFAULT_DETERGENT_AMOUNT,
    DEFAULT_DRY_LEVEL,
    DEFAULT_RINSE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SOFTENER_AMOUNT,
    DEFAULT_SPIN,
    DEFAULT_TEMP,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class SamsungWasherCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Polls SmartThings API and exposes parsed washer state."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: SmartThingsWasherAPI,
        device_label: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.device_label = device_label

        # Stores user intent for next Start — local state, not from device.
        self.selected_cycle:            str = CYCLE_REGULAR_WASH_NAME
        self.selected_dry_level:        str = DEFAULT_DRY_LEVEL
        self.selected_temp:             str = DEFAULT_TEMP
        self.selected_spin:             str = DEFAULT_SPIN
        self.selected_rinse:            str = DEFAULT_RINSE
        self.selected_softener_amount:  str = DEFAULT_SOFTENER_AMOUNT
        self.selected_detergent_amount: str = DEFAULT_DETERGENT_AMOUNT

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            raw = await self.api.get_status()
        except CannotConnect as err:
            raise UpdateFailed(f"Cannot reach SmartThings: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err
        return self._parse(raw)

    @staticmethod
    def _parse(raw: dict) -> dict[str, Any]:
        """Flatten the nested SmartThings status JSON into a flat dict."""
        main = raw.get("components", {}).get("main", {})
        hca  = raw.get("components", {}).get("hca.main", {})

        def v(cap: str, attr: str) -> Any:
            """Get .value from main component capability attribute."""
            return main.get(cap, {}).get(attr, {}).get("value")

        # Machine state: prefer samsungce extended, fall back to standard
        machine_state = v("samsungce.washerOperatingState", "operatingState") \
                     or v("washerOperatingState", "machineState")

        job_state = v("samsungce.washerOperatingState", "washerJobState") \
                 or v("washerOperatingState", "washerJobState")

        # Current cycle: strip "Table_XX_" prefix for readability
        raw_cycle: str | None = v("samsungce.washerCycle", "washerCycle")
        current_cycle = raw_cycle.split("_", 2)[-1] if raw_cycle else None  # e.g. "Course_20"

        return {
            # Operating state
            "machine_state":        machine_state,
            "job_state":            job_state,
            "completion_time":      v("washerOperatingState", "completionTime"),
            # Progress
            "progress":             v("samsungce.washerOperatingState", "progress"),
            "remaining_time":       v("samsungce.washerOperatingState", "remainingTime"),
            "remaining_time_str":   v("samsungce.washerOperatingState", "remainingTimeStr"),
            "washing_progress":     v("samsungce.washerOperatingState", "washingProgress"),
            "drying_progress":      v("samsungce.washerOperatingState", "dryingProgress"),
            # Cycle
            "current_cycle":        current_cycle,
            "cycle_type":           v("samsungce.washerCycle", "cycleType"),
            # Current settings (read from device)
            "water_temp":           v("custom.washerWaterTemperature", "washerWaterTemperature"),
            "spin_level":           v("custom.washerSpinLevel", "washerSpinLevel"),
            "rinse_cycles":         v("custom.washerRinseCycles", "washerRinseCycles"),
            "dry_level":            v("custom.dryerDryLevel", "dryerDryLevel"),
            # Control
            "remote_enabled":       v("remoteControlStatus", "remoteControlEnabled"),
            # Dispense amounts (auto-dispense)
            "softener_amount":      v("samsungce.autoDispenseSoftener",  "amount"),
            "detergent_amount":     v("samsungce.autoDispenseDetergent", "amount"),
            # HCA mode (quick wash lives here)
            "hca_mode":             hca.get("hca.washerMode", {}).get("mode", {}).get("value"),
        }
