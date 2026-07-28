"""Application credentials for Samsung Washer — returns custom OAuth2 implementation."""
from homeassistant.components.application_credentials import (
    AuthorizationServer,
    ClientCredential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import AbstractOAuth2Implementation

from .config_flow import SmartThingsOAuth2Implementation


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    return AuthorizationServer(
        authorize_url="https://api.smartthings.com/oauth/authorize",
        token_url="https://api.smartthings.com/oauth/token",
    )


async def async_get_auth_implementation(
    hass: HomeAssistant,
    auth_domain: str,
    credential: ClientCredential,
) -> AbstractOAuth2Implementation:
    """Return our custom implementation that fixes SmartThings token exchange."""
    return SmartThingsOAuth2Implementation(
        hass,
        credential.client_id,
        credential.client_secret,
    )
