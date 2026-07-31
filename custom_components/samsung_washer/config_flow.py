"""Config flow for Samsung Washer — direct token entry (no OAuth redirect)."""
from __future__ import annotations

import logging
import time
from typing import Any

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.config_entry_oauth2_flow import (
    AbstractOAuth2Implementation,
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
    VALID_DRY_LEVELS_AIO,
    VALID_RINSES,
    VALID_SPINS,
    VALID_TEMPS,
)

_LOGGER = logging.getLogger(__name__)

_TOKEN_URL = "https://api.smartthings.com/oauth/token"
_DEVICES_URL = "https://api.smartthings.com/v1/devices"


class SmartThingsOAuth2Implementation(AbstractOAuth2Implementation):
    """
    OAuth2 implementation that stores client credentials and handles
    token refresh. No OAuth redirect — tokens are pasted directly.
    """

    def __init__(self, hass: HomeAssistant, client_id: str, client_secret: str) -> None:
        self._hass          = hass
        self._client_id     = client_id
        self._client_secret = client_secret

    @property
    def name(self) -> str:
        return "SmartThings"

    @property
    def domain(self) -> str:
        return DOMAIN

    @property
    def extra_authorize_data(self) -> dict:
        return {}

    async def async_generate_authorize_url(self, flow_id: str) -> str:
        raise NotImplementedError("Direct token entry; no OAuth redirect")

    async def async_resolve_external_data(self, external_data: Any) -> dict:
        raise NotImplementedError("Direct token entry; no OAuth redirect")

    async def _async_refresh_token(self, token: dict) -> dict:
        """Refresh the access token using Basic Auth — matches Insomnia."""
        import base64
        credentials = base64.b64encode(
            f"{self._client_id}:{self._client_secret}".encode("ascii")
        ).decode("ascii")

        async with aiohttp.ClientSession() as session:
            async with session.post(
                _TOKEN_URL,
                data={
                    "grant_type":    "refresh_token",
                    "refresh_token": token["refresh_token"],
                },
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type":  "application/x-www-form-urlencoded",
                },
            ) as resp:
                resp.raise_for_status()
                new_token = await resp.json()

        return {
            **token,
            **new_token,
            "expires_at": time.time() + new_token.get("expires_in", 86399),
        }


# ── Config flow ───────────────────────────────────────────────────────────────

_CONF_ACCESS_TOKEN  = "access_token"
_CONF_REFRESH_TOKEN = "refresh_token"


class SamsungWasherConfigFlow(ConfigFlow, domain=DOMAIN):
    """
    Config flow:
      Step 1  — enter client_id + client_secret
      Step 2  — paste access_token + refresh_token
      Step 3  — confirm device (auto-discovered or manual)
    """

    VERSION = 1

    def __init__(self) -> None:
        super().__init__()
        self._client_id:     str = ""
        self._client_secret: str = ""
        self._access_token:  str = ""
        self._refresh_token: str = ""
        self._discovered:    dict[str, str] = {}

    @property
    def logger(self) -> logging.Logger:
        return _LOGGER

    # ── Step 1: client credentials ────────────────────────────────────────────

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        errors: dict[str, str] = {}

        if user_input is not None:
            self._client_id     = user_input[CONF_CLIENT_ID].strip()
            self._client_secret = user_input[CONF_CLIENT_SECRET].strip()
            return await self.async_step_tokens()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_CLIENT_ID):     str,
                vol.Required(CONF_CLIENT_SECRET): str,
            }),
            errors=errors,
        )

    # ── Step 2: paste tokens ──────────────────────────────────────────────────

    async def async_step_tokens(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        """Ask for access_token + refresh_token obtained from SmartThings."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._access_token  = user_input[_CONF_ACCESS_TOKEN].strip()
            self._refresh_token = user_input[_CONF_REFRESH_TOKEN].strip()

            # Validate by discovering devices
            try:
                devices = await self._fetch_washers(self._access_token)
            except aiohttp.ClientResponseError as err:
                if err.status in (401, 403):
                    errors["base"] = "invalid_access_token"
                else:
                    errors["base"] = "cannot_connect"
                devices = []
            except Exception:
                _LOGGER.exception("Device discovery error")
                errors["base"] = "unknown"
                devices = []

            if not errors:
                self._discovered = {d["deviceId"]: d["label"] for d in devices}
                return await self.async_step_device()

        return self.async_show_form(
            step_id="tokens",
            data_schema=vol.Schema({
                vol.Required(_CONF_ACCESS_TOKEN):  str,
                vol.Required(_CONF_REFRESH_TOKEN): str,
            }),
            description_placeholders={
                "hint": "Get these from Insomnia by exchanging an auth code manually."
            },
            errors=errors,
        )

    # ── Step 3: pick device ───────────────────────────────────────────────────

    async def async_step_device(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        if user_input is not None:
            device_id = user_input[CONF_DEVICE_ID].strip()
            label = self._discovered.get(device_id, "Samsung Washer")

            # Register implementation so OAuth2Session can refresh later
            async_register_implementation(
                self.hass,
                DOMAIN,
                SmartThingsOAuth2Implementation(
                    self.hass, self._client_id, self._client_secret
                ),
            )

            return self.async_create_entry(
                title=label,
                data={
                    CONF_CLIENT_ID:     self._client_id,
                    CONF_CLIENT_SECRET: self._client_secret,
                    CONF_DEVICE_ID:     device_id,
                    "auth_implementation": DOMAIN,
                    "token": {
                        "access_token":  self._access_token,
                        "refresh_token": self._refresh_token,
                        "token_type":    "Bearer",
                        "expires_in":    86399,
                        "expires_at":    time.time() + 86399,
                    },
                },
            )

        if self._discovered:
            options = {k: f"{v} ({k})" for k, v in self._discovered.items()}
            schema = vol.Schema({vol.Required(CONF_DEVICE_ID): vol.In(options)})
        else:
            schema = vol.Schema({
                vol.Required(CONF_DEVICE_ID, default=DEFAULT_DEVICE_ID): str
            })

        return self.async_show_form(step_id="device", data_schema=schema)

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    async def _fetch_washers(token: str) -> list[dict]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                _DEVICES_URL,
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
        self._entry    = config_entry
        self._settings = {}   # holds general settings between steps

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        """Step 1 — general settings."""
        if user_input is not None:
            self._settings = user_input
            return await self.async_step_cycles()

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

    async def async_step_cycles(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        """Step 2 — rename cycles."""
        from . import cycles as cycles_mod

        all_cycles = cycles_mod.load(self._entry.options)
        overrides  = self._entry.options.get("cycle_names", {})

        if user_input is not None:
            # Rebuild cycle_names dict from flat form values
            cycle_names = {
                c["code"]: user_input.get(f"cycle_{c['code']}", c["name"])
                for c in all_cycles
            }
            return self.async_create_entry(
                title="",
                data={**self._settings, "cycle_names": cycle_names},
            )

        # Build one text field per cycle: key = "cycle_Course_XX", default = current name
        fields = {
            vol.Optional(
                f"cycle_{c['code']}",
                default=overrides.get(c["code"], c["name"]),
            ): str
            for c in all_cycles
        }
        return self.async_show_form(
            step_id="cycles",
            data_schema=vol.Schema(fields),
        )

