from __future__ import annotations
import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from .const import CONF_IP_ADDRESS, CONF_TOKEN, CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL
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

        # Get polling interval from config entry data or options
        polling_interval = entry.options.get(
            CONF_POLLING_INTERVAL,
            entry.data.get(CONF_POLLING_INTERVAL, DEFAULT_POLLING_INTERVAL)
        )

        super().__init__(
            hass,
            _LOGGER,
            name="Jung Home",
            update_interval=timedelta(seconds=polling_interval),
        )

    async def _async_update_data(self) -> dict:
        """Fetch devices and their current states from Jung Home API."""
        try:
            # Get device list
            devices = await asyncio.wait_for(
                JunghomeGateway.request_devices(self.ip, self.token),
                timeout=30.0
            )
            
            if devices is None:
                raise UpdateFailed("Failed to get devices from Jung Home API")
            
            # Fetch current state for each device
            for device in devices:
                await self._fetch_device_state(device)
            
            self._devices = devices
            return {"devices": devices}
            
        except asyncio.TimeoutError as err:
            raise UpdateFailed(f"Timeout connecting to Jung Home hub at {self.ip}") from err
        except Exception as err:
            if "401" in str(err) or "Unauthorized" in str(err):
                raise ConfigEntryAuthFailed(f"Authentication failed: {err}") from err
            raise UpdateFailed(f"Error communicating with Jung Home API: {err}") from err

    async def _fetch_device_state(self, device: dict) -> None:
        """Fetch current state for a single device."""
        device_id = device["id"]
        device_type = device["type"]
        
        try:
            # Handle covers (Position/PositionAndAngle)
            if device_type in ["Position", "PositionAndAngle"]:
                level_datapoint = self._find_datapoint(device, "level")
                if level_datapoint:
                    state_data = await self._get_datapoint_state(device_id, level_datapoint["id"])
                    if state_data and "values" in state_data and state_data["values"]:
                        level_value = int(state_data["values"][0]["value"])
                        device["current_position"] = 100 - level_value  # Jung Home uses inverted scale
                    else:
                        device["current_position"] = 50  # Default fallback
                        
            # Handle lights (OnOff/DimmerLight/ColorLight/Socket)
            elif device_type in ["OnOff", "DimmerLight", "ColorLight", "Socket"]:
                switch_datapoint = self._find_datapoint(device, "switch")
                if switch_datapoint:
                    state_data = await self._get_datapoint_state(device_id, switch_datapoint["id"])
                    if state_data and "values" in state_data and state_data["values"]:
                        switch_value = bool(int(state_data["values"][0]["value"]))
                        device["is_on"] = switch_value
                    else:
                        device["is_on"] = False  # Default fallback
                        
                # Also get brightness for dimmable lights
                if device_type in ["DimmerLight", "ColorLight"]:
                    brightness_datapoint = self._find_datapoint(device, "brightness")
                    if brightness_datapoint:
                        state_data = await self._get_datapoint_state(device_id, brightness_datapoint["id"])
                        if state_data and "values" in state_data and state_data["values"]:
                            brightness_value = int(state_data["values"][0]["value"])
                            device["brightness"] = int((brightness_value / 100) * 255)  # Convert to HA scale
                        else:
                            device["brightness"] = 255 if device.get("is_on") else 0
                            
        except Exception as err:
            _LOGGER.warning("Failed to fetch state for device %s: %s", device_id, err)
            # Set defaults on error
            if device_type in ["Position", "PositionAndAngle"]:
                device["current_position"] = 50
            elif device_type in ["OnOff", "DimmerLight", "ColorLight", "Socket"]:
                device["is_on"] = False
                if device_type in ["DimmerLight", "ColorLight"]:
                    device["brightness"] = 0

    def _find_datapoint(self, device: dict, datapoint_type: str) -> dict | None:
        """Find a datapoint of specific type in device."""
        for datapoint in device.get("datapoints", []):
            if datapoint.get("type") == datapoint_type:
                return datapoint
        return None

    async def _get_datapoint_state(self, device_id: str, datapoint_id: str) -> dict | None:
        """Get current state of a specific datapoint."""
        url = f'https://{self.ip}/api/junghome/functions/{device_id}/datapoints/{datapoint_id}'
        try:
            return await asyncio.wait_for(
                JunghomeGateway.http_get_request(url, self.token),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            _LOGGER.warning("Timeout getting state for datapoint %s", datapoint_id)
            return None

    @property
    def devices(self) -> list | None:
        """Return the devices data."""
        return self._devices

    def get_device_by_id(self, device_id: str) -> dict | None:
        """Get device data by device ID."""
        if self.data and "devices" in self.data:
            for device in self.data["devices"]:
                if device["id"] == device_id:
                    return device
        return None

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