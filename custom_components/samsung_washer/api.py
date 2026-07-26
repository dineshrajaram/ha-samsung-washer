"""Async SmartThings REST API client — uses HA OAuth2Session."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import aiohttp
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session

from .const import (
    CYCLE_ALL_IN_ONE,
    CYCLE_DRYING_ONLY,
    DEFAULT_DRY_LEVEL,
    DEFAULT_RINSE,
    DEFAULT_SPIN,
    DEFAULT_TEMP,
)

_LOGGER = logging.getLogger(__name__)

_BASE = "https://api.smartthings.com/v1"


class CannotConnect(Exception):
    """Raised when the API is unreachable."""


class InvalidAuth(Exception):
    """Raised when the token is rejected."""


class SmartThingsWasherAPI:
    """Thin async wrapper — auth is handled by OAuth2Session (auto-refresh)."""

    def __init__(self, session: OAuth2Session, device_id: str) -> None:
        self._session = session
        self._device_id = device_id

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _url(self, path: str = "") -> str:
        return f"{_BASE}/devices/{self._device_id}{path}"

    def _cmd(
        self,
        capability: str,
        command: str,
        arguments: list | None = None,
        component: str = "main",
    ) -> dict[str, Any]:
        c: dict[str, Any] = {
            "component": component,
            "capability": capability,
            "command": command,
        }
        if arguments is not None:
            c["arguments"] = arguments
        return c

    async def _post(self, commands: list[dict]) -> dict:
        try:
            resp = await self._session.async_request(
                "POST",
                self._url("/commands"),
                json={"commands": commands},
            )
            if resp.status in (401, 403):
                raise InvalidAuth
            resp.raise_for_status()
            return await resp.json()
        except aiohttp.ClientConnectionError as err:
            raise CannotConnect(str(err)) from err

    # ── Status ────────────────────────────────────────────────────────────────

    async def get_status(self) -> dict[str, Any]:
        try:
            resp = await self._session.async_request("GET", self._url("/status"))
            if resp.status in (401, 403):
                raise InvalidAuth
            resp.raise_for_status()
            return await resp.json()
        except aiohttp.ClientConnectionError as err:
            raise CannotConnect(str(err)) from err

    # ── Machine control ───────────────────────────────────────────────────────

    async def _start(self) -> None:
        try:
            await self._post([self._cmd("samsungce.washerOperatingState", "start")])
        except aiohttp.ClientResponseError as err:
            _LOGGER.debug("samsungce start failed (%s), trying legacy", err.status)
            await self._post([
                self._cmd("washerOperatingState", "setMachineState", ["run"])
            ])

    async def stop(self) -> None:
        try:
            await self._post([self._cmd("samsungce.washerOperatingState", "cancel")])
        except aiohttp.ClientResponseError as err:
            _LOGGER.debug("samsungce cancel failed (%s), trying legacy", err.status)
            await self._post([
                self._cmd("washerOperatingState", "setMachineState", ["stop"])
            ])

    async def pause(self) -> None:
        await self._post([self._cmd("samsungce.washerOperatingState", "pause")])

    # ── Cycle sequences ───────────────────────────────────────────────────────

    async def start_all_in_one(
        self,
        water_temp: str = DEFAULT_TEMP,
        spin_level: str = DEFAULT_SPIN,
        rinse_cycles: str = DEFAULT_RINSE,
        dry_level: str = DEFAULT_DRY_LEVEL,
    ) -> None:
        _LOGGER.debug(
            "all-in-one: temp=%s spin=%s rinse=%s dry=%s",
            water_temp, spin_level, rinse_cycles, dry_level,
        )
        await self._post([
            self._cmd("samsungce.washerCycle", "setWasherCycle", [CYCLE_ALL_IN_ONE])
        ])
        await asyncio.sleep(1)
        await self._post([
            self._cmd("custom.washerWaterTemperature", "setWasherWaterTemperature", [water_temp]),
            self._cmd("custom.washerSpinLevel",        "setWasherSpinLevel",        [spin_level]),
            self._cmd("custom.washerRinseCycles",      "setWasherRinseCycles",      [rinse_cycles]),
            self._cmd("custom.dryerDryLevel",          "setDryerDryLevel",          [dry_level]),
        ])
        await asyncio.sleep(1)
        await self._start()

    async def start_drying_only(self, dry_level: str = "cupboard") -> None:
        _LOGGER.debug("drying-only: level=%s", dry_level)
        await self._post([
            self._cmd("samsungce.washerCycle", "setWasherCycle", [CYCLE_DRYING_ONLY])
        ])
        await asyncio.sleep(1)
        await self._post([
            self._cmd("custom.dryerDryLevel", "setDryerDryLevel", [dry_level])
        ])
        await asyncio.sleep(1)
        await self._start()

    async def start_quick_15(self) -> None:
        _LOGGER.debug("quick-15: setMode quickWash")
        try:
            await self._post([
                self._cmd("hca.washerMode", "setMode", ["quickWash"], component="hca.main")
            ])
        except aiohttp.ClientResponseError as err:
            _LOGGER.warning("setMode failed (%s), retrying with setWasherMode", err.status)
            await self._post([
                self._cmd("hca.washerMode", "setWasherMode", ["quickWash"], component="hca.main")
            ])
        await asyncio.sleep(1)
        await self._start()
