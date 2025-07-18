"""Platform for sensor integration."""
from __future__ import annotations
import asyncio
import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity, DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MANUFACTURER
from . import JunghomeConfigEntry
from .junghome_client import JunghomeGateway

_LOGGER = logging.getLogger(__name__)


class JunghomeHubConfigCoordinator(DataUpdateCoordinator):
    """Jung Home hub configuration update coordinator."""

    def __init__(self, hass: HomeAssistant, ip: str, token: str) -> None:
        """Initialize the coordinator."""
        self.ip = ip
        self.token = token

        super().__init__(
            hass,
            _LOGGER,
            name="Jung Home Hub Config",
            update_interval=timedelta(minutes=5),  # Update every 5 minutes
        )

    async def _async_update_data(self) -> dict:
        """Fetch hub configuration from Jung Home API."""
        try:
            config = await asyncio.wait_for(
                JunghomeGateway.request_hub_config(self.ip, self.token),
                timeout=30.0
            )
            
            if config is None:
                raise Exception("Failed to get hub configuration from Jung Home API")
            
            return config
            
        except asyncio.TimeoutError as err:
            raise Exception(f"Timeout connecting to Jung Home hub at {self.ip}") from err
        except Exception as err:
            raise Exception(f"Error communicating with Jung Home API: {err}") from err


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JunghomeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jung Home hub sensors from a config entry."""
    
    # Get main coordinator to extract IP and token
    main_coordinator = config_entry.runtime_data
    
    # Create hub config coordinator
    hub_coordinator = JunghomeHubConfigCoordinator(
        hass, main_coordinator.ip, main_coordinator.token
    )
    
    # Initial data fetch
    await hub_coordinator.async_config_entry_first_refresh()
    
    # Create sensor entities
    sensors = [
        JunghomeCloudStateSensor(hub_coordinator),
        JunghomeIPAddressSensor(hub_coordinator),
        JunghomeVersionSensor(hub_coordinator),
    ]
    
    async_add_entities(sensors)


class JunghomeHubSensorBase(CoordinatorEntity, SensorEntity):
    """Base class for Jung Home hub sensors."""

    def __init__(self, coordinator: JunghomeHubConfigCoordinator, sensor_type: str, name: str) -> None:
        """Initialize a Jung Home hub sensor."""
        super().__init__(coordinator)
        
        self._sensor_type = sensor_type
        self._attr_unique_id = f"junghome_hub_{sensor_type}"
        self._attr_name = name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        config = self.coordinator.data or {}
        return DeviceInfo(
            identifiers={(DOMAIN, "hub")},
            name="Jung Home Gateway",
            model="Gateway",
            manufacturer=MANUFACTURER,
            sw_version=config.get("version_release", "Unknown"),
            serial_number=config.get("system_serial", "Unknown"),
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()


class JunghomeCloudStateSensor(JunghomeHubSensorBase):
    """Jung Home cloud state sensor."""

    def __init__(self, coordinator: JunghomeHubConfigCoordinator) -> None:
        """Initialize the cloud state sensor."""
        super().__init__(coordinator, "cloud_state", "Cloud State")

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        config = self.coordinator.data or {}
        if config.get("cloud_register", False):
            return "registered"
        return "not_registered"

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        config = self.coordinator.data or {}
        return {
            "cloud_username": config.get("cloud_username", ""),
            "cloud_connect": config.get("cloud_connect", False),
            "cloud_register": config.get("cloud_register", False),
        }

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        config = self.coordinator.data or {}
        if config.get("cloud_register", False):
            return "mdi:cloud-check"
        return "mdi:cloud-off"




class JunghomeIPAddressSensor(JunghomeHubSensorBase):
    """Jung Home IP address sensor."""

    def __init__(self, coordinator: JunghomeHubConfigCoordinator) -> None:
        """Initialize the IP address sensor."""
        super().__init__(coordinator, "ip_address", "IP Address")

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        config = self.coordinator.data or {}
        return config.get("ip_address", "Unknown")

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        config = self.coordinator.data or {}
        return {
            "dhcp": config.get("ip_dhcp", False),
            "subnet": config.get("ip_subnet", ""),
            "dns": config.get("ip_dns", ""),
            "gateway": config.get("ip_gateway", ""),
            "mac_address": config.get("ip_mac", ""),
        }

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        return "mdi:ip-network"




class JunghomeVersionSensor(JunghomeHubSensorBase):
    """Jung Home version sensor."""

    def __init__(self, coordinator: JunghomeHubConfigCoordinator) -> None:
        """Initialize the version sensor."""
        super().__init__(coordinator, "version", "Version")

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        config = self.coordinator.data or {}
        return config.get("version_release", "Unknown")

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        config = self.coordinator.data or {}
        return {
            "build": config.get("version_build", ""),
            "is_beta": config.get("version_beta", False),
            "smartphone_version": config.get("version_smartphone", "0"),
        }

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        return "mdi:information"


