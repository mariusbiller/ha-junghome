from __future__ import annotations
import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from .const import CONF_IP_ADDRESS, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .junghome_client import JunghomeGateway

_LOGGER = logging.getLogger(__name__)

class JunghomeCoordinator(DataUpdateCoordinator):
    """Jung Home data update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.ip = entry.data[CONF_IP_ADDRESS]
        self.token = entry.data[CONF_TOKEN]
        self._devices = None

        super().__init__(
            hass,
            _LOGGER,
            name="Jung Home",
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> dict:
        """Fetch data from Jung Home API."""
        try:
            # Test basic connectivity first
            devices = await asyncio.wait_for(
                JunghomeGateway.request_devices(self.ip, self.token),
                timeout=30.0
            )
            
            if devices is None:
                raise UpdateFailed("Failed to get devices from Jung Home API")
            
            self._devices = devices
            return {"devices": devices}
            
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout connecting to Jung Home hub at {self.ip}") from err
        except Exception as err:
            if "401" in str(err) or "Unauthorized" in str(err):
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
            raise UpdateFailed(f"Error communicating with Jung Home API: {err}") from err

    @property
    def devices(self) -> list | None:
        """Return the devices data."""
        return self._devices

    async def test_connection(self) -> bool:
        """Test connection to the Jung Home hub."""
        try:
            devices = await asyncio.wait_for(
                JunghomeGateway.request_devices(self.ip, self.token),
                timeout=30.0
            )
            return devices is not None
        except Exception as err:
            _LOGGER.debug("Connection test failed: %s", err)
            return False