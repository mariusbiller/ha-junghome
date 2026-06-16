"""Platform for button integration."""
from __future__ import annotations
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JunghomeConfigEntry
from .datapoints import get_datapoint_id
from .entity import JunghomeDeviceEntity

_LOGGER = logging.getLogger(__name__)

ROCKER_SWITCH_TYPES = ["Rocker Switch", "RockerSwitch"]
ROCKER_BUTTONS = {
    "up_request": "Up",
    "down_request": "Down",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JunghomeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jung Home rocker switch buttons from a config entry."""
    coordinator = config_entry.runtime_data
    _LOGGER.info("Initialize Jung Home buttons from coordinator")

    async def add_new_buttons(devices):
        """Add new button devices dynamically."""
        buttons = []
        for device in devices:
            if device["type"] not in ROCKER_SWITCH_TYPES:
                continue

            for datapoint_type, label_suffix in ROCKER_BUTTONS.items():
                datapoint_id = get_datapoint_id(device, datapoint_type)
                if datapoint_id is None:
                    continue

                buttons.append(
                    JunghomeRockerButton(
                        coordinator,
                        device,
                        datapoint_id,
                        datapoint_type,
                        label_suffix,
                    )
                )

        if buttons:
            _LOGGER.info("Adding %d new button entities", len(buttons))
            async_add_entities(buttons)

    coordinator.register_entity_callback("button", add_new_buttons)

    if coordinator.data is None or "devices" not in coordinator.data:
        _LOGGER.warning("No device data available from coordinator")
        return

    await add_new_buttons(coordinator.data["devices"])


class JunghomeRockerButton(JunghomeDeviceEntity, ButtonEntity):
    """Jung Home rocker switch button."""

    def __init__(
        self,
        coordinator,
        device,
        datapoint_id: str,
        datapoint_type: str,
        label_suffix: str,
    ) -> None:
        """Initialize a Jung Home rocker switch button."""
        super().__init__(coordinator)
        self._device_id = device["id"]
        self._datapoint_id = datapoint_id
        self._datapoint_type = datapoint_type
        self._label_suffix = label_suffix

        self._attr_unique_id = f"{self._device_id}_{self._datapoint_id}"
        self._attr_name = f"{device['label']} {self._label_suffix}"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sync_label_and_area()
        device = self.coordinator.get_device_by_id(self._device_id)
        self._sync_rocker_label(device)

        if self._is_pressed_from_device(device):
            self.hass.async_create_task(self._async_press_action())
        else:
            self.async_write_ha_state()

    @property
    def device_info(self):
        """Return device info."""
        return self._build_device_info("Rocker Switch")

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        attributes = super().extra_state_attributes
        attributes["datapoint_id"] = self._datapoint_id
        attributes["datapoint_type"] = self._datapoint_type
        return attributes

    async def async_press(self) -> None:
        """Handle a Home Assistant button press service call."""
        return None

    def _sync_rocker_label(self, device: dict | None) -> None:
        """Update entity label while keeping the rocker direction suffix."""
        if not device:
            return

        label = device.get("label")
        if label:
            self._attr_name = f"{label} {self._label_suffix}"

    def _is_pressed_from_device(self, device: dict | None) -> bool:
        """Return True if the latest rocker datapoint value is pressed."""
        if not device:
            return False
        return bool(device.get("states", {}).get(self._datapoint_type, False))
