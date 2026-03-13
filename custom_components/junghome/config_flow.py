from __future__ import annotations

import ipaddress
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries, exceptions
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .const import DOMAIN  # pylint:disable=unused-import
from .const import CONF_IP_ADDRESS, CONF_TOKEN
from .hub import Hub

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

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._discovered_ip: str | None = None

    # No options flow needed for WebSocket-based integration

    def _is_configured_ip(self, ip_address: str) -> bool:
        """Return True if the IP address is already configured."""
        normalized_ip = ip_address.strip().lower()
        for entry in self._async_current_entries():
            entry_ip = str(entry.data.get(CONF_IP_ADDRESS, "")).strip().lower()
            if entry.unique_id == normalized_ip or entry_ip == normalized_ip:
                return True
        return False

    def _get_data_schema(self, user_input: dict[str, Any] | None = None) -> vol.Schema:
        """Return the config form schema with discovery defaults applied."""
        suggested_values = dict(user_input or {})
        if (
            self._discovered_ip
            and not self._is_configured_ip(self._discovered_ip)
            and CONF_IP_ADDRESS not in suggested_values
        ):
            suggested_values[CONF_IP_ADDRESS] = self._discovered_ip
        return self.add_suggested_values_to_schema(DATA_SCHEMA, suggested_values)

    async def _async_handle_discovery(
        self, host: str | None
    ) -> config_entries.ConfigFlowResult:
        """Store the discovered host and continue in the user step."""
        if host:
            self._discovered_ip = host.strip()
            if self._is_configured_ip(self._discovered_ip):
                return self.async_abort(reason="already_configured")
            await self.async_set_unique_id(self._discovered_ip.lower())
            self._abort_if_unique_id_configured()
        return await self.async_step_user()

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle DHCP discovery."""
        return await self._async_handle_discovery(discovery_info.ip)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> config_entries.ConfigFlowResult:
        """Handle zeroconf discovery."""
        return await self._async_handle_discovery(discovery_info.host)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                unique_id = user_input[CONF_IP_ADDRESS].strip().lower()
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                info = await validate_input(self.hass, user_input)
                # Store the trimmed token
                clean_data = user_input.copy()
                clean_data[CONF_IP_ADDRESS] = clean_data[CONF_IP_ADDRESS].strip()
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
            step_id="user", data_schema=self._get_data_schema(user_input), errors=errors
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidIP(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid IP."""


class InvalidToken(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid token."""
