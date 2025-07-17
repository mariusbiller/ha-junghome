from __future__ import annotations
from typing import Any
import voluptuous as vol
from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from .const import DOMAIN  # pylint:disable=unused-import
from .hub import Hub
from .const import CONF_IP_ADDRESS, CONF_TOKEN
import logging
_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_IP_ADDRESS): str,
    vol.Required(CONF_TOKEN): str,
})


async def validate_input(hass: HomeAssistant, data: dict) -> dict[str, Any]:
    if len(data[CONF_IP_ADDRESS]) < 3:
        raise InvalidIP

    hub = Hub(hass, data[CONF_IP_ADDRESS], data[CONF_TOKEN])
    await hub.async_initialize()
    
    result = await hub.test_connection()
    if not result:
        raise CannotConnect

    return {"title": data[CONF_IP_ADDRESS]}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hello World."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
                return self.async_create_entry(title=info["title"], data=user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidIP:
                errors[CONF_IP_ADDRESS] = "invalid_ip"
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