"""Platform for binary sensor integration."""
from __future__ import annotations
import asyncio
import logging
from datetime import timedelta

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from . import JunghomeConfigEntry
from .sensor import JunghomeHubConfigCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JunghomeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jung Home hub binary sensors from a config entry."""
    
    # Get main coordinator to extract IP and token
    main_coordinator = config_entry.runtime_data
    
    # Create hub config coordinator (reuse from sensor.py)
    hub_coordinator = JunghomeHubConfigCoordinator(
        hass, main_coordinator.ip, main_coordinator.token
    )
    
    # Initial data fetch
    await hub_coordinator.async_config_entry_first_refresh()
    
    # Create binary sensor entities
    binary_sensors = [
        JunghomeCloudErrorBinarySensor(hub_coordinator),
        JunghomeConnectionBinarySensor(hub_coordinator),
        JunghomeUpdateBinarySensor(hub_coordinator),
    ]
    
    async_add_entities(binary_sensors)


class JunghomeHubBinarySensorBase(CoordinatorEntity, BinarySensorEntity):
    """Base class for Jung Home hub binary sensors."""

    def __init__(self, coordinator: JunghomeHubConfigCoordinator, sensor_type: str, name: str) -> None:
        """Initialize a Jung Home hub binary sensor."""
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


class JunghomeCloudErrorBinarySensor(JunghomeHubBinarySensorBase):
    """Jung Home cloud error binary sensor."""

    def __init__(self, coordinator: JunghomeHubConfigCoordinator) -> None:
        """Initialize the cloud error binary sensor."""
        super().__init__(coordinator, "cloud_problem", "Cloud Problem")
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        """Return true if there is a cloud error (problem detected)."""
        config = self.coordinator.data or {}
        return config.get("cloud_error", False)


class JunghomeConnectionBinarySensor(JunghomeHubBinarySensorBase):
    """Jung Home connectivity binary sensor."""

    def __init__(self, coordinator: JunghomeHubConfigCoordinator) -> None:
        """Initialize the connectivity binary sensor."""
        super().__init__(coordinator, "connectivity", "Connectivity")
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Return true if connected (no IP error)."""
        config = self.coordinator.data or {}
        return not config.get("ip_error", True)


class JunghomeUpdateBinarySensor(JunghomeHubBinarySensorBase):
    """Jung Home update available binary sensor."""

    def __init__(self, coordinator: JunghomeHubConfigCoordinator) -> None:
        """Initialize the update binary sensor."""
        super().__init__(coordinator, "update", "Update Available")
        self._attr_device_class = BinarySensorDeviceClass.UPDATE

    @property
    def is_on(self) -> bool:
        """Return true if update is available (version NOT up to date)."""
        config = self.coordinator.data or {}
        return not config.get("version_up_to_date", True)

    @property
    def extra_state_attributes(self) -> dict:
        """Return the state attributes."""
        config = self.coordinator.data or {}
        return {
            "auto_update": config.get("update_auto", False),
            "update_progress": config.get("update_progress", "0"),
            "update_download": config.get("update_download", "0"),
            "current_version": config.get("version_release", "Unknown"),
            "current_build": config.get("version_build", "Unknown"),
        }