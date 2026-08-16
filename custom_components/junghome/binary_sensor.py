"""Platform for binary sensor integration."""
from __future__ import annotations
import logging

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from . import JunghomeConfigEntry
from .button import ROCKER_BUTTONS, ROCKER_SWITCH_TYPES
from .datapoints import get_datapoint_id
from .entity import JunghomeDeviceEntity
from .sensor import JunghomeHubConfigCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JunghomeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jung Home hub and rocker switch binary sensors from a config entry."""

    # Get main coordinator to extract IP and token
    main_coordinator = config_entry.runtime_data

    async def add_new_rocker_sensors(devices):
        """Add "held" sensors for new rocker switch devices dynamically."""
        sensors = []
        for device in devices:
            if device["type"] not in ROCKER_SWITCH_TYPES:
                continue

            for datapoint_type, label_suffix in ROCKER_BUTTONS.items():
                datapoint_id = get_datapoint_id(device, datapoint_type)
                if datapoint_id is None:
                    continue

                sensors.append(
                    JunghomeRockerHeldSensor(
                        main_coordinator,
                        device,
                        datapoint_id,
                        datapoint_type,
                        label_suffix,
                    )
                )

        if sensors:
            _LOGGER.info("Adding %d new rocker held sensors", len(sensors))
            async_add_entities(sensors)

    main_coordinator.register_entity_callback("binary_sensor", add_new_rocker_sensors)

    if main_coordinator.data and "devices" in main_coordinator.data:
        await add_new_rocker_sensors(main_coordinator.data["devices"])
    else:
        _LOGGER.warning("No device data available from coordinator")

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
        hub_id = config.get("ip_address") or "hub"
        return DeviceInfo(
            identifiers={(DOMAIN, hub_id)},
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


class JunghomeRockerHeldSensor(JunghomeDeviceEntity, BinarySensorEntity):
    """On while a rocker switch direction is physically held down.

    The gateway sends "1" on press and "0" on release with no repeats in
    between, so this is simply the last value of the request datapoint. The
    matching button entity records the press; this one exposes the release
    edge that a button state (a timestamp) cannot carry.
    """

    def __init__(
        self,
        coordinator,
        device,
        datapoint_id: str,
        datapoint_type: str,
        label_suffix: str,
    ) -> None:
        """Initialize a Jung Home rocker held sensor."""
        super().__init__(coordinator)
        self._device_id = device["id"]
        self._datapoint_id = datapoint_id
        self._datapoint_type = datapoint_type
        self._label_suffix = f"{label_suffix} Held"

        self._attr_unique_id = f"{self._device_id}_{self._datapoint_id}_held"
        self._attr_name = f"{device['label']} {self._label_suffix}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sync_label_and_area()
        self._sync_rocker_label()
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return self._build_device_info("Rocker Switch")

    @property
    def is_on(self) -> bool:
        """Return True while the rocker direction is held."""
        return bool(self._get_device().get("states", {}).get(self._datapoint_type, False))

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        attributes = super().extra_state_attributes
        attributes["datapoint_id"] = self._datapoint_id
        attributes["datapoint_type"] = self._datapoint_type
        return attributes

    def _sync_rocker_label(self) -> None:
        """Re-append the direction suffix that _sync_label_and_area strips."""
        label = self._get_device().get("label")
        if label:
            self._attr_name = f"{label} {self._label_suffix}"
