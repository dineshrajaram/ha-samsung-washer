"""application_credentials platform — kept for compatibility but not used.

Credentials are now collected directly in the config flow (Step 1).
"""
from homeassistant.components.application_credentials import AuthorizationServer
from homeassistant.core import HomeAssistant


async def async_get_authorization_server(hass: HomeAssistant) -> AuthorizationServer:
    return AuthorizationServer(
        authorize_url="https://api.smartthings.com/oauth/authorize",
        token_url="https://api.smartthings.com/oauth/token",
    )
