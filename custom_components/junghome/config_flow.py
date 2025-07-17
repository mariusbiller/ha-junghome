from __future__ import annotations
from typing import Any
import voluptuous as vol
from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from .const import DOMAIN  # pylint:disable=unused-import
from .hub import Hub
from .const import CONF_IP_ADDRESS, CONF_TOKEN, CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL
import logging
_LOGGER = logging.getLogger(__name__)


DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_IP_ADDRESS): str,
    vol.Required(CONF_TOKEN): str,
    vol.Optional(CONF_POLLING_INTERVAL, default=DEFAULT_POLLING_INTERVAL): vol.All(
        vol.Coerce(int), vol.Range(min=5, max=300)
    ),
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
    """Handle a config flow for Jung Home."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_PUSH

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return OptionsFlowHandler(config_entry)

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


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Jung Home options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({
            vol.Optional(
                CONF_POLLING_INTERVAL, 
                default=self.config_entry.options.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)
            ): vol.All(vol.Coerce(int), vol.Range(min=5, max=300)),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema
        )