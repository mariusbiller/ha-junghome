from __future__ import annotations
from typing import Any
import voluptuous as vol
import ipaddress
from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from .const import DOMAIN  # pylint:disable=unused-import
from .hub import Hub
from .const import CONF_IP_ADDRESS, CONF_TOKEN
import logging
_LOGGER = logging.getLogger(__name__)


def validate_ip_address(value):
    """Validate that the value is a valid IP address."""
    try:
        ipaddress.ip_address(value)
        return value
    except ValueError:
        raise vol.Invalid("Invalid IP address")


def validate_token(value):
    """Validate that the token is not empty."""
    if not value or not value.strip():
        raise vol.Invalid("Token cannot be empty")
    return value.strip()


DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_IP_ADDRESS): vol.All(str, validate_ip_address),
    vol.Required(CONF_TOKEN): vol.All(str, validate_token),
})


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    hub = Hub(hass, data[CONF_IP_ADDRESS], data[CONF_TOKEN])
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
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except vol.Invalid as err:
                # Handle validation errors from the schema
                if "Invalid IP address" in str(err):
                    errors[CONF_IP_ADDRESS] = "invalid_ip"
                elif "Token cannot be empty" in str(err):
                    errors[CONF_TOKEN] = "invalid_token"
                else:
                    errors["base"] = "invalid_input"
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