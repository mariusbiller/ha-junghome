from __future__ import annotations
from typing import Any
import asyncio
import random
from typing import Callable
from .junghome_client import JunghomeGateway as junghome
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import HubConfigEntry
from .const import (DOMAIN, MANUFACTURER)
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
        
        # get state_id
        state_id = None
        for datapoint in device.get("datapoints", []):
            if datapoint.get("type") == "level":
                state_id = datapoint.get("id")
                break
        
        
        # init cover class
        covers.append(WindowCover( device.get("id"), state_id, device.get("label"), hub))
    
    # Add all entities to HA
    async_add_entities(covers)


#
# WINDOW COVER
#
class WindowCover(CoverEntity):
    should_poll = False
    supported_features = CoverEntityFeature.SET_POSITION | CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, device_id: str, state_id: str, name: str, hub: Hub) -> None:
        self._device_id = device_id 
        self.roller_id = state_id
        self._ip = hub.ip
        self._token = hub.token
        self._id = device_id
        self.name = name
        self._callbacks = set()
        self.position = 65
        self.moving = 0  # >0 is up, <0 is down

        self._attr_unique_id = f"{self.roller_id}_cover"
        self._attr_name = self.name
        
        _LOGGER.error(f"Initialized Roller: {self.name} with ID {self._id}")

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        # Importantly for a push integration, the module that will be getting updates
        # needs to notify HA of changes. The device has a registercallback
        # method, so to this we add the 'self.async_write_ha_state' method, to be
        # called where ever there are changes.
        self._callbacks.add(self.async_write_ha_state)
        _LOGGER.debug(f"Callback registered for Roller {self.name}")

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self._callbacks.discard(self.async_write_ha_state)
        _LOGGER.debug(f"Callback removed for Roller {self.name}")

    # Information about the parent device visible in the UI.
    @property
    def device_info(self) -> DeviceInfo:
        return {
            "identifiers": {(DOMAIN, self.roller_id)},
            "name": self.name,  
            "sw_version": "0.0.0",
            "model": "WindowCover",
            "manufacturer": MANUFACTURER,
        }

    # shows if device is online or not
    @property
    def available(self) -> bool:
        online = True # fake online state
        return online

    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self.position

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed, same as position 0."""
        return self.position == 0

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self.moving < 0

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self.moving > 0


    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        self.position  = 0
        
        """Set the cover position."""
        url = f'https://{self._ip}/api/junghome/functions/{self._device_id}/datapoints/{self.roller_id}'
        body = {
            "data": [{
                        "key": "level",
                        "value": str(int(self.position))
                    }]
        }
        response = await junghome.http_patch_request(url, self._token, body)
        if response is None: print("failed to move on cover.")


    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        self.position  = 100
        
        """Set the cover position."""
        url = f'https://{self._ip}/api/junghome/functions/{self._device_id}/datapoints/{self.roller_id}'
        body = {
            "data": [{
                        "key": "level",
                        "value": str(int(self.position))
                    }]
        }
        response = await junghome.http_patch_request(url, self._token, body)
        if response is None: print("failed to move on cover.")


    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position."""
        self.position  = int(kwargs[ATTR_POSITION])
        url = f'https://{self._ip}/api/junghome/functions/{self._device_id}/datapoints/{self.roller_id}'
        body = {
            "data": [{
                        "key": "level",
                        "value": str(int(self.position))
                    }]
        }
        response = await junghome.http_patch_request(url, self._token, body)
        if response is None: print("failed to move on cover.")


    async def publish_updates(self) -> None:
        """Schedule call all registered callbacks."""
        self.position = 30
        _LOGGER.debug(f"Roller {self.name} updated position to {self.position}")
        for callback in self._callbacks:
            callback()

