"""Config flow for Samsung Washer — OAuth2 via SmartThings."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2FlowHandler,
    AbstractOAuth2Implementation,
    LocalOAuth2Implementation,
)

from .const import (
    CONF_DEFAULT_DRY,
    CONF_DEFAULT_RINSE,
    CONF_DEFAULT_SPIN,
    CONF_DEFAULT_TEMP,
    CONF_DEVICE_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_DEVICE_ID,
    DEFAULT_DRY_LEVEL,
    DEFAULT_RINSE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SPIN,
    DEFAULT_TEMP,
    DOMAIN,
    OAUTH_SCOPES,
    VALID_DRY_LEVELS_AIO,
    VALID_RINSES,
    VALID_SPINS,
    VALID_TEMPS,
)

_LOGGER = logging.getLogger(__name__)

_BASE = "https://api.smartthings.com/v1"


_TOKEN_URL     = "https://api.smartthings.com/oauth/token"
_AUTHORIZE_URL = "https://api.smartthings.com/oauth/authorize"
_REDIRECT_URI  = "https://my.home-assistant.io/redirect/oauth"


class SmartThingsOAuth2Implementation(LocalOAuth2Implementation):
    """
    Custom token exchange for SmartThings.

    HA's default LocalOAuth2Implementation sends client_id in BOTH the
    Basic Auth header AND the request body. SmartThings rejects that with
    a 401. This override sends client_id only in Basic Auth, matching what
    a plain curl / Insomnia request does.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        client_id: str,
        client_secret: str,
    ) -> None:
        super().__init__(
            hass,
            DOMAIN,
            client_id,
            client_secret,
            _AUTHORIZE_URL,
            _TOKEN_URL,
        )

    @property
    def redirect_uri(self) -> str:
        return _REDIRECT_URI

    async def _async_resolve_auth_code(
        self, code: str, redirect_uri: str
    ) -> dict[str, Any]:
        """Exchange auth code for tokens — client_id only in Basic Auth."""
        session = aiohttp_client.async_get_clientsession(self.hass)
        resp = await session.post(
            _TOKEN_URL,
            data={
                "grant_type":   "authorization_code",
                "code":         code,
                "redirect_uri": redirect_uri,
            },
            auth=aiohttp.BasicAuth(self.client_id, self.client_secret),
        )
        resp.raise_for_status()
        return await resp.json()


class SamsungWasherConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """OAuth2 config flow — redirects to SmartThings, then asks for device."""

    VERSION = 1
    DOMAIN = DOMAIN

    def __init__(self) -> None:
        super().__init__()
        self._oauth_data: dict = {}
        self._discovered: dict[str, str] = {}

    @property
    def logger(self) -> logging.Logger:
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        return {"scope": OAUTH_SCOPES}

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> dict:
        """Called after SmartThings OAuth completes. Discover washer devices."""
        self._oauth_data = data
        token = data["token"]["access_token"]

        try:
            devices = await self._fetch_washers(token)
        except Exception:
            _LOGGER.exception("Failed to discover washer devices")
            devices = []

        if len(devices) == 1:
            # Only one washer — use it automatically
            device = devices[0]
            return self.async_create_entry(
                title=device["label"],
                data={**data, CONF_DEVICE_ID: device["deviceId"]},
            )

        # Multiple or zero washers — let user pick / enter manually
        self._discovered = {d["deviceId"]: d["label"] for d in devices}
        return await self.async_step_device()

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        """Step to select or confirm the washer device."""
        errors: dict[str, str] = {}

        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID].strip()
            label = self._discovered.get(device_id, "Samsung Washer")
            return self.async_create_entry(
                title=label,
                data={**self._oauth_data, CONF_DEVICE_ID: device_id},
            )

        # Build schema: dropdown if devices discovered, text field otherwise
        if self._discovered:
            options = {k: f"{v} ({k})" for k, v in self._discovered.items()}
            device_schema = vol.Schema({
                vol.Required(CONF_DEVICE_ID): vol.In(options)
            })
        else:
            device_schema = vol.Schema({
                vol.Required(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): str
            })

        return self.async_show_form(
            step_id="device",
            data_schema=device_schema,
            errors=errors,
        )

    @staticmethod
    async def _fetch_washers(token: str) -> list[dict]:
        """Fetch devices with washerOperatingState capability."""
        import aiohttp as _aiohttp
        headers = {"Authorization": f"Bearer {token}"}
        async with _aiohttp.ClientSession() as session:
            async with session.get(
                f"{_BASE}/devices",
                headers=headers,
                params={"capability": "washerOperatingState"},
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                return data.get("items", [])

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SamsungWasherOptionsFlow(config_entry)


class SamsungWasherOptionsFlow(OptionsFlow):
    """Options flow — scan interval and all-in-one defaults."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._entry.options
        schema = vol.Schema({
            vol.Optional(
                CONF_SCAN_INTERVAL,
                default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            ): vol.All(int, vol.Range(min=10, max=300)),
            vol.Optional(
                CONF_DEFAULT_TEMP,
                default=current.get(CONF_DEFAULT_TEMP, DEFAULT_TEMP),
            ): vol.In(VALID_TEMPS),
            vol.Optional(
                CONF_DEFAULT_SPIN,
                default=current.get(CONF_DEFAULT_SPIN, DEFAULT_SPIN),
            ): vol.In(VALID_SPINS),
            vol.Optional(
                CONF_DEFAULT_RINSE,
                default=current.get(CONF_DEFAULT_RINSE, DEFAULT_RINSE),
            ): vol.In(VALID_RINSES),
            vol.Optional(
                CONF_DEFAULT_DRY,
                default=current.get(CONF_DEFAULT_DRY, DEFAULT_DRY_LEVEL),
            ): vol.In(VALID_DRY_LEVELS_AIO),
        })

        return self.async_show_form(step_id="init", data_schema=schema)
