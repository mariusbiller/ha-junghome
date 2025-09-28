from __future__ import annotations
from typing import Any
import voluptuous as vol
import ipaddress
from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN  # pylint:disable=unused-import
from .hub import Hub
from .const import CONF_IP_ADDRESS, CONF_TOKEN
import logging
_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_IP_ADDRESS): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
})


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    # Validate IP address
    try:
        ipaddress.ip_address(data[CONF_IP_ADDRESS])
    except ValueError:
        raise InvalidIP
    
    # Validate token is not empty
    if not data[CONF_TOKEN] or not data[CONF_TOKEN].strip():
        raise InvalidToken
    
    # Test connection
    hub = Hub(hass, data[CONF_IP_ADDRESS], data[CONF_TOKEN].strip())
    await hub.async_initialize()
    
    result = await hub.test_connection()
    if not result:
        raise CannotConnect

    return {"title": data[CONF_IP_ADDRESS]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Jung Home."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    # No options flow needed for WebSocket-based integration

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                # Store the trimmed token
                clean_data = user_input.copy()
                clean_data[CONF_TOKEN] = clean_data[CONF_TOKEN].strip()
                return self.async_create_entry(title=info["title"], data=clean_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidIP:
                errors[CONF_IP_ADDRESS] = "invalid_ip"
            except InvalidToken:
                errors[CONF_TOKEN] = "invalid_token"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidIP(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid IP."""


class InvalidToken(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid token."""