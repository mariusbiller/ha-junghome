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
from .junghome_client import JunghomeGateway

_LOGGER = logging.getLogger(__name__)


IP_SCHEMA = vol.Schema({
    vol.Required(CONF_IP_ADDRESS): cv.string,
})

TOKEN_SCHEMA = vol.Schema({
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
        self._ip_address: str | None = None
        self._suggested_token: str | None = None
        self._registration_error: str | None = None
        self._registration_task = None

    # No options flow needed for WebSocket-based integration

    def _is_configured_ip(self, ip_address: str) -> bool:
        """Return True if the IP address is already configured."""
        normalized_ip = ip_address.strip().lower()
        for entry in self._async_current_entries():
            entry_ip = str(entry.data.get(CONF_IP_ADDRESS, "")).strip().lower()
            if entry.unique_id == normalized_ip or entry_ip == normalized_ip:
                return True
        return False

    def _get_ip_schema(self, user_input: dict[str, Any] | None = None) -> vol.Schema:
        """Return the IP step schema with discovery defaults applied."""
        suggested_values = dict(user_input or {})
        if (
            self._discovered_ip
            and not self._is_configured_ip(self._discovered_ip)
            and CONF_IP_ADDRESS not in suggested_values
        ):
            suggested_values[CONF_IP_ADDRESS] = self._discovered_ip
        return self.add_suggested_values_to_schema(IP_SCHEMA, suggested_values)

    def _get_token_schema(self, user_input: dict[str, Any] | None = None) -> vol.Schema:
        """Return the token step schema."""
        suggested_values = dict(user_input or {})
        if self._suggested_token and CONF_TOKEN not in suggested_values:
            suggested_values[CONF_TOKEN] = self._suggested_token
        return self.add_suggested_values_to_schema(TOKEN_SCHEMA, suggested_values)

    async def _async_register_token(self) -> None:
        """Request a token from the gateway after the user presses the button."""
        self._registration_error = None
        self._suggested_token = await JunghomeGateway.request_registration_token(
            self._ip_address,
            "home assistant",
        )
        if self._suggested_token is None:
            self._registration_error = "register_failed"

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
        """Handle the IP address step."""
        errors = {}
        if user_input is not None:
            try:
                ip_address = user_input[CONF_IP_ADDRESS].strip()
                ipaddress.ip_address(ip_address)
                await self.async_set_unique_id(ip_address.lower())
                self._abort_if_unique_id_configured()
                self._ip_address = ip_address
                self._suggested_token = None
                self._registration_error = None
                self._registration_task = None
                return await self.async_step_token_register()
            except InvalidIP:
                errors[CONF_IP_ADDRESS] = "invalid_ip"
            except ValueError:
                errors[CONF_IP_ADDRESS] = "invalid_ip"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=self._get_ip_schema(user_input), errors=errors
        )

    async def async_step_token_register(self, user_input=None):
        """Wait for the automatic gateway registration request to complete."""
        if self._ip_address is None:
            return await self.async_step_user()

        if self._registration_task is None:
            self._registration_task = self.hass.async_create_task(
                self._async_register_token()
            )
        if not self._registration_task.done():
            return self.async_show_progress(
                step_id="token_register",
                progress_action="press_gateway_button",
                progress_task=self._registration_task,
                description_placeholders={"ip_address": self._ip_address},
            )

        await self._registration_task
        self._registration_task = None
        return self.async_show_progress_done(next_step_id="token")

    async def async_step_token(self, user_input=None):
        """Handle the token step."""
        if self._ip_address is None:
            return await self.async_step_user()

        errors = {}
        if self._registration_error:
            errors["base"] = self._registration_error
            self._registration_error = None

        if user_input is not None:
            try:
                clean_data = {
                    CONF_IP_ADDRESS: self._ip_address,
                    CONF_TOKEN: user_input[CONF_TOKEN].strip(),
                }
                info = await validate_input(self.hass, clean_data)
                return self.async_create_entry(title=info["title"], data=clean_data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidToken:
                errors[CONF_TOKEN] = "invalid_token"
            except InvalidIP:
                errors["base"] = "invalid_ip"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="token",
            data_schema=self._get_token_schema(user_input),
            errors=errors,
            description_placeholders={"ip_address": self._ip_address},
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidIP(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid IP."""


class InvalidToken(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid token."""
