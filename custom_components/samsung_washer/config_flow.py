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
    async_register_implementation,
)

from .const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
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

_TOKEN_URL     = "https://api.smartthings.com/oauth/token"
_AUTHORIZE_URL = "https://api.smartthings.com/oauth/authorize"
_REDIRECT_URI  = "https://my.home-assistant.io/redirect/oauth"


class SmartThingsOAuth2Implementation(LocalOAuth2Implementation):
    """
    Custom token exchange — client_id only in Basic Auth, not in body.

    SmartThings rejects requests that include client_id in both the
    Authorization header and the form body. Standard HA LocalOAuth2Implementation
    sends it in both. This class sends it only in Basic Auth.
    """

    def __init__(self, hass: HomeAssistant, client_id: str, client_secret: str) -> None:
        super().__init__(
            hass, DOMAIN, client_id, client_secret, _AUTHORIZE_URL, _TOKEN_URL
        )

    @property
    def name(self) -> str:
        return "SmartThings"

    @property
    def redirect_uri(self) -> str:
        return _REDIRECT_URI

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        return {"scope": OAUTH_SCOPES}

    async def _async_resolve_auth_code(
        self, code: str, redirect_uri: str
    ) -> dict[str, Any]:
        """Exchange auth code — client_id in Basic Auth only, no body duplication."""
        import base64
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("ascii")
        ).decode("ascii")

        session = aiohttp_client.async_get_clientsession(self.hass)
        resp = await session.post(
            _TOKEN_URL,
            data={
                "grant_type":   "authorization_code",
                "code":         code,
                "redirect_uri": redirect_uri,
            },
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type":  "application/x-www-form-urlencoded",
            },
        )
        resp.raise_for_status()
        return await resp.json()

    async def async_refresh_token(self, token: dict) -> dict:
        """Refresh access token — same Basic Auth pattern."""
        import base64
        credentials = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("ascii")
        ).decode("ascii")

        session = aiohttp_client.async_get_clientsession(self.hass)
        resp = await session.post(
            _TOKEN_URL,
            data={
                "grant_type":    "refresh_token",
                "refresh_token": token["refresh_token"],
            },
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type":  "application/x-www-form-urlencoded",
            },
        )
        resp.raise_for_status()
        new_token = await resp.json()
        return {**token, **new_token}


# ── Config flow ───────────────────────────────────────────────────────────────

class SamsungWasherConfigFlow(AbstractOAuth2FlowHandler, domain=DOMAIN):
    """
    Two-step flow:
      1. User enters client_id + client_secret
      2. OAuth redirect to SmartThings → device selection
    """

    VERSION = 1
    DOMAIN  = DOMAIN

    def __init__(self) -> None:
        super().__init__()
        self._client_id:     str = ""
        self._client_secret: str = ""
        self._oauth_data:    dict = {}
        self._discovered:    dict[str, str] = {}

    @property
    def logger(self) -> logging.Logger:
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, str]:
        return {"scope": OAUTH_SCOPES}

    # ── Step 1: collect credentials ───────────────────────────────────────────

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._client_id     = user_input[CONF_CLIENT_ID].strip()
            self._client_secret = user_input[CONF_CLIENT_SECRET].strip()

            # Register our implementation so pick_implementation finds it
            async_register_implementation(
                self.hass,
                DOMAIN,
                SmartThingsOAuth2Implementation(
                    self.hass, self._client_id, self._client_secret
                ),
            )
            return await self.async_step_pick_implementation()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_CLIENT_ID):     str,
                vol.Required(CONF_CLIENT_SECRET): str,
            }),
            errors=errors,
        )

    # ── Step 2: after OAuth completes → discover device ───────────────────────

    async def async_oauth_create_entry(self, data: dict[str, Any]) -> dict:
        self._oauth_data = {
            **data,
            CONF_CLIENT_ID:     self._client_id,
            CONF_CLIENT_SECRET: self._client_secret,
        }
        token = data["token"]["access_token"]

        try:
            devices = await self._fetch_washers(token)
        except Exception:
            _LOGGER.exception("Device discovery failed")
            devices = []

        if len(devices) == 1:
            device = devices[0]
            return self.async_create_entry(
                title=device["label"],
                data={**self._oauth_data, CONF_DEVICE_ID: device["deviceId"]},
            )

        self._discovered = {d["deviceId"]: d["label"] for d in devices}
        return await self.async_step_device()

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID].strip()
            label = self._discovered.get(device_id, "Samsung Washer")
            return self.async_create_entry(
                title=label,
                data={**self._oauth_data, CONF_DEVICE_ID: device_id},
            )

        if self._discovered:
            options = {k: f"{v} ({k})" for k, v in self._discovered.items()}
            schema = vol.Schema({vol.Required(CONF_DEVICE_ID): vol.In(options)})
        else:
            schema = vol.Schema({
                vol.Required(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): str
            })

        return self.async_show_form(step_id="device", data_schema=schema)

    @staticmethod
    async def _fetch_washers(token: str) -> list[dict]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.smartthings.com/v1/devices",
                headers={"Authorization": f"Bearer {token}"},
                params={"capability": "washerOperatingState"},
            ) as resp:
                resp.raise_for_status()
                return (await resp.json()).get("items", [])

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return SamsungWasherOptionsFlow(config_entry)


# ── Options flow ──────────────────────────────────────────────────────────────

class SamsungWasherOptionsFlow(OptionsFlow):
    def __init__(self, config_entry: ConfigEntry) -> None:
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._entry.options
        schema = vol.Schema({
            vol.Optional(CONF_SCAN_INTERVAL,
                         default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                         ): vol.All(int, vol.Range(min=10, max=300)),
            vol.Optional(CONF_DEFAULT_TEMP,
                         default=current.get(CONF_DEFAULT_TEMP, DEFAULT_TEMP),
                         ): vol.In(VALID_TEMPS),
            vol.Optional(CONF_DEFAULT_SPIN,
                         default=current.get(CONF_DEFAULT_SPIN, DEFAULT_SPIN),
                         ): vol.In(VALID_SPINS),
            vol.Optional(CONF_DEFAULT_RINSE,
                         default=current.get(CONF_DEFAULT_RINSE, DEFAULT_RINSE),
                         ): vol.In(VALID_RINSES),
            vol.Optional(CONF_DEFAULT_DRY,
                         default=current.get(CONF_DEFAULT_DRY, DEFAULT_DRY_LEVEL),
                         ): vol.In(VALID_DRY_LEVELS_AIO),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
