from __future__ import annotations
from typing import Any
import asyncio
import random
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .junghome_client import JunghomeGateway as junghome
from . import HubConfigEntry
from .const import DOMAIN, MANUFACTURER
from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverEntityFeature,
    CoverEntity,
)
import logging
_LOGGER = logging.getLogger(__name__)

#
# Setup
#
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HubConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
   
    # The hub is loaded from entry runtime_data that was set by __init__.py
    hub = config_entry.runtime_data
    _LOGGER.info(f"Initialize {hub.ip} WindowCovers from hub")
    
    # Get JUNG HOME devices
    devices = await junghome.request_devices(hub.ip, hub.token)

    # check devices 
    if devices is None:
        _LOGGER.info("Failed to retrieve cover devices. API response was None.")
        hub.online = False
        return

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
        covers.append(WindowCover(device.get("id"), state_id, device.get("label"), hub))
    
    async_add_entities(covers)


#
# WINDOW COVER
#
class WindowCover(CoverEntity):
    should_poll = True
    supported_features = (
        CoverEntityFeature.SET_POSITION | CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE
    )

    # INIT
    def __init__(self, device_id: str, state_id: str, name: str, hub: HubConfigEntry) -> None:
        self._device_id = device_id
        self.roller_id = state_id
        self._ip = hub.ip
        self._token = hub.token
        self.name = name

        # Initialize state variables
        self.position = 50  # starting position (example)
        self.moving = 0     # positive for opening, negative for closing

        self._attr_unique_id = f"{self.roller_id}_cover"
        self._attr_name = self.name
        
        _LOGGER.debug(f"Initialized cover: {self.name} with ID {self._device_id}")
    
    
    # GET INFO
    @property
    def device_info(self) -> DeviceInfo:
        info = {
            "identifiers": {(DOMAIN, self.roller_id)},
            "name": self.name,
            "model": "WindowCover",
            "manufacturer": MANUFACTURER,
        }
        return info


    # GET ONLINE
    @property
    def available(self) -> bool:
        online = True # fake always online state
        return online


    # GET POSITION
    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self.position


    # GET CLOSED
    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed, same as position 0."""
        return self.position == 0
        

    # SET OPEN
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Set position."""
        self.position = 100
        
        """Open the cover."""
        url = f'https://{self._ip}/api/junghome/functions/{self._device_id}/datapoints/{self.roller_id}'
        body = {
            "data": [{
                "key": "level",
                "value": "0"
            }]
        }
        response = await junghome.http_patch_request(url, self._token, body)
        if response is None: print("failed to move on cover.")


    # SET CLOSE
    async def async_close_cover(self, **kwargs: Any) -> None:
        """Set position."""
        self.position = 0
        
        """Close the cover."""
        url = f'https://{self._ip}/api/junghome/functions/{self._device_id}/datapoints/{self.roller_id}'
        body = {
            "data": [{
                "key": "level",
                "value": "100"
            }]
        }
        response = await junghome.http_patch_request(url, self._token, body)
        if response is None: print("failed to move on cover.")


    # SET POSITION
    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set position."""
        self.position  = int(kwargs[ATTR_POSITION])
        
        """ Change the cover position """
        url = f'https://{self._ip}/api/junghome/functions/{self._device_id}/datapoints/{self.roller_id}'
        body = {
            "data": [{
                "key": "level",
                "value": str(100-int(self.position))
            }]
        }
        response = await junghome.http_patch_request(url, self._token, body)
        if response is None: print("failed to move on cover.")
        
    
    # GET POSITION
    async def async_update(self) -> None:
        """
        Fetch new state for this cover.
        This is the only method that should fetch new data for Home Assistant.
        """
        url = f'https://{self._ip}/api/junghome/functions/{self._device_id}/datapoints/{self.roller_id}'
        headers = {
            'accept': 'application/json',
            'token': self._token
        }
        
        response = await junghome.http_get_request(url, self._token)
        if response is None: 
            print("failed get state of cover.")
            return None
        
        value_str = response['values'][0]['value']
        self.position = 100 - int(value_str)



