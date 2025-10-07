"""Platform for switch integration."""
from __future__ import annotations
import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import JunghomeConfigEntry
from .const import DOMAIN, MANUFACTURER
from .junghome_client import JunghomeGateway

_LOGGER = logging.getLogger(__name__)

#
# Setup
#
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JunghomeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jung Home switches from a config entry."""

    coordinator = config_entry.runtime_data
    _LOGGER.info("Initialize Jung Home switches from coordinator")

    # Register callback for dynamic device addition
    async def add_new_switches(devices):
        """Add new switch devices dynamically."""
        switches: list[JunghomeSwitch] = []
        for device in devices:
            # skip non-socket devices
            if device.get("type") != "Socket":
                continue

            # get switch_id
            switch_id = None
            for datapoint in device.get("datapoints", []):
                if datapoint.get("type") == "switch":
                    switch_id = datapoint.get("id")
                    break

            if switch_id is None:
                continue

            switches.append(JunghomeSwitch(coordinator, device, switch_id))

        if switches:
            _LOGGER.info("Adding %d new switch entities", len(switches))
            async_add_entities(switches)

    coordinator.register_entity_callback("switch", add_new_switches)

    if coordinator.data is None or "devices" not in coordinator.data:
        _LOGGER.warning("No device data available from coordinator")
        return

    devices = coordinator.data["devices"]
    await add_new_switches(devices)

#
# SWITCH
#
class JunghomeSwitch(CoordinatorEntity, SwitchEntity):
    """Jung Home switch entity for socket devices."""

    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(self, coordinator, device, switch_id: str) -> None:
        """Initialize a Jung Home Switch."""
        super().__init__(coordinator)

        self._device_id = device["id"]
        self._switch_id = switch_id

        self._attr_unique_id = f"{self._device_id}"
        self._attr_name = device["label"]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._attr_name,
            model="Socket",
            manufacturer=MANUFACTURER,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device:
            return device.get("available", True)
        return False

    # GET ON/OFF   
    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device:
            return device.get("is_on", False)
        return False

    # SET ON
    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        url = f"https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._switch_id}"
        body = {"data": [{"key": "switch", "value": "1"}]}
        response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
        if response is None:
            _LOGGER.error("Failed to turn on switch %s", self._device_id)

    # SET OFF
    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        url = f"https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._switch_id}"
        body = {"data": [{"key": "switch", "value": "0"}]}
        response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
        if response is None:
            _LOGGER.error("Failed to turn off switch %s", self._device_id)

