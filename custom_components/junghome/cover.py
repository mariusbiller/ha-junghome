from __future__ import annotations
from typing import Any
import logging

from homeassistant.core import HomeAssistant
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
    
    # Get devices from coordinator data
    if coordinator.data is None or "devices" not in coordinator.data:
        _LOGGER.warning("No device data available from coordinator")
        return
        
    devices = coordinator.data["devices"]

    # add cover devices
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
    
    async_add_entities(covers)


#
# WINDOW COVER
#
class JunghomeCover(CoordinatorEntity, CoverEntity):
    """Jung Home cover entity."""
    
    _attr_supported_features = (
        CoverEntityFeature.SET_POSITION | CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    )

    def __init__(self, coordinator, device, state_id: str) -> None:
        """Initialize a Jung Home Cover."""
        super().__init__(coordinator)
        
        self._device = device
        self._device_id = device["id"]
        self._state_id = state_id
        self.position = 50
        
        self._attr_unique_id = f"{self._device_id}"
        self._attr_name = device["label"]

    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._attr_name,
            model="WindowCover",
            manufacturer=MANUFACTURER,
        )




    # GET POSITION
    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self.position


    # GET OPEN/CLOSED
    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed, same as position 0."""
        return self.position == 0
        

    # SET OPEN
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Set position."""
        self.position = 100
        
        """Open the cover."""
        url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._state_id}'
        body = {
            "data": [{
                "key": "level",
                "value": "0"
            }]
        }
        response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
        if response is None: print("failed to move on cover.")


    # SET CLOSE
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Set position."""
        self.position = 0
        
        """Close the cover."""
        url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._state_id}'
        body = {
            "data": [{
                "key": "level",
                "value": "100"
            }]
        }
        response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
        if response is None: print("failed to move on cover.")


    # SET POSITION
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set position."""
        self.position  = int(kwargs[ATTR_POSITION])
        
        """ Change the cover position """
        url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._state_id}'
        body = {
            "data": [{
                "key": "level",
                "value": str(100-int(self.position))
            }]
        }
        response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
        if response is None: print("failed to move on cover.")
        
    
    # GET POSITION
    async def async_update(self) -> None:
        """
        Fetch new state for this cover.
        This is the only method that should fetch new data for Home Assistant.
        """
        url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._state_id}'
        
        response = await JunghomeGateway.http_get_request(url, self.coordinator.token)
        if response is None: 
            print("failed get state of cover.")
            return None
        
        value_str = response['values'][0]['value']
        self.position = 100 - int(value_str)



