"""Platform for switch integration."""
from __future__ import annotations
import logging

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JunghomeConfigEntry
from .datapoints import get_datapoint_id
from .entity import JunghomeDeviceEntity
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

    async def add_new_switches(devices):
        """Add new switch devices dynamically."""
        switches = []
        for device in devices:
            if device["type"] not in ["Socket", "SocketEnergy"]:
                continue

            switch_id = get_datapoint_id(device, "switch")

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
class JunghomeSwitch(JunghomeDeviceEntity, SwitchEntity):
    """Jung Home switch entity"""

    _attr_device_class = SwitchDeviceClass.OUTLET

    def __init__(self, coordinator, device, switch_id: str) -> None:
        """Initialize a Jung Home Switch."""
        super().__init__(coordinator)
        self._device_id = device["id"]
        self._switch_id = switch_id
        # Per JUNG HOME documentation, device_id is unique across installations and device resets.
        self._attr_unique_id = f"{self._device_id}"
        self._attr_name = device["label"]

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sync_label_and_area()
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return device info."""
        return self._build_device_info("Socket")

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device:
            return device.get("is_on", False)
        return False

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._switch_id}'
        body = {"data": [{"key": "switch", "value": "1"}]}
        response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
        if response is None:
            _LOGGER.error("Failed to turn on switch %s", self._device_id)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._switch_id}'
        body = {"data": [{"key": "switch", "value": "0"}]}
        response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
        if response is None:
            _LOGGER.error("Failed to turn off switch %s", self._device_id)
