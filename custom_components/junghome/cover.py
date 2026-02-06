from __future__ import annotations
from typing import Any
import logging

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntityFeature,
    CoverEntity,
)

from .const import DOMAIN, MANUFACTURER
from . import JunghomeConfigEntry
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
    """Set up Jung Home covers from a config entry."""
   
    # The coordinator is loaded from entry runtime_data that was set by __init__.py
    coordinator = config_entry.runtime_data
    _LOGGER.info("Initialize Jung Home covers from coordinator")
    
    # Register callback for dynamic device addition
    async def add_new_covers(devices):
        """Add new cover devices dynamically."""
        covers = []
        for device in devices:
            # skip non-cover devices 
            if device["type"] not in ["Position", "PositionAndAngle"]:
                continue
            
            # Find the state id for the cover position
            state_id = None
            for datapoint in device.get("datapoints", []):
                if datapoint.get("type") == "level":
                    state_id = datapoint.get("id")
                    break
            
            # Create the cover entity
            covers.append(JunghomeCover(coordinator, device, state_id))
        
        if covers:
            _LOGGER.info("Adding %d new cover entities", len(covers))
            async_add_entities(covers)
    
    coordinator.register_entity_callback("cover", add_new_covers)
    
    # Get initial devices from coordinator data
    if coordinator.data is None or "devices" not in coordinator.data:
        _LOGGER.warning("No device data available from coordinator")
        return
        
    devices = coordinator.data["devices"]

    # add cover devices
    await add_new_covers(devices)


#
# WINDOW COVER
#
class JunghomeCover(CoordinatorEntity, CoverEntity):
    """Jung Home cover entity."""
    
    _attr_supported_features = (
        CoverEntityFeature.SET_POSITION | CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    def __init__(self, coordinator, device, state_id: str) -> None:
        """Initialize a Jung Home Cover."""
        super().__init__(coordinator)
        
        self._device_id = device["id"]
        self._state_id = state_id
        
        # Per JUNG HOME documentation, device_id is unique across installations and device resets.
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
            model="WindowCover",
            manufacturer=MANUFACTURER,
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device:
            return device.get("available", True)
        return False



    # GET POSITION
    @property 
    def current_cover_position(self):
        """Return the current position of the cover."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device:
            return device.get("current_position", 50)
        return 50

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed, same as position 0."""
        return self.current_cover_position == 0

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device:
            return device.get("level_move", 0) == -1
        return False

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device:
            return device.get("level_move", 0) == 1
        return False

    # SET OPEN
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._state_id}'
        body = {
            "data": [{
                "key": "level",
                "value": "0"
            }]
        }
        response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
        if response is None: 
            _LOGGER.error("Failed to open cover %s", self._device_id)


    # SET CLOSE
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._state_id}'
        body = {
            "data": [{
                "key": "level",
                "value": "100"
            }]
        }
        response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
        if response is None: 
            _LOGGER.error("Failed to close cover %s", self._device_id)


    # SET POSITION
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set cover position."""
        position = int(kwargs[ATTR_POSITION])
        url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._state_id}'
        body = {
            "data": [{
                "key": "level",
                "value": str(100-position)
            }]
        }
        response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
        if response is None: 
            _LOGGER.error("Failed to set cover position %s", self._device_id)


    # STOP COVER
    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover movement."""
        # Only send stop command if cover is currently moving
        device = self.coordinator.get_device_by_id(self._device_id)
        if device and device.get("level_move", 0) != 0:
            url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._state_id}'
            body = {
                "data": [{
                    "key": "level_move",
                    "value": "0"
                }]
            }
            response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
            if response is None: 
                _LOGGER.error("Failed to stop cover %s", self._device_id)
        else:
            _LOGGER.debug("Cover %s is not moving, no stop command sent", self._device_id)


