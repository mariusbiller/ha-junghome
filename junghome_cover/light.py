"""Platform for light integration."""
from __future__ import annotations
import logging
import voluptuous as vol
from .junghome_client import JunghomeGateway as junghome
import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (ATTR_BRIGHTNESS, PLATFORM_SCHEMA, LightEntity, ColorMode)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.entity import DeviceInfo
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
    _LOGGER.info(f"Initialize {hub.ip} Light from hub")
    
    # Get JUNG HOME devices
    devices = await junghome.request_devices(hub.ip, hub.token)

    # check devices 
    if devices is None:
        _LOGGER.info("Failed to retrieve cover devices. API response was None.")
        hub.online = False
        return
    
    # add light devices
    lights = []
    for device in devices:
    
        # skip non-light devices 
        light_types = ["OnOff", "DimmerLight", "ColorLight", "Socket"] 
        if device["type"] not in light_types:
            continue
        
        # get switch_id
        switch_id = None
        for datapoint in device.get("datapoints", []):
            if datapoint.get("type") == "switch":
                switch_id = datapoint.get("id")
                break
            
        # Skip no switch datapoint
        if switch_id is None:
            continue  
            
        # get brightness_id
        brightness_id = None
        for datapoint in device.get("datapoints", []):
            if datapoint.get("type") == "brightness":
                brightness_id = datapoint.get("id")
                break
        
        # compose device info
        device_info = {
            "name": device["label"],
            "device_id": device["id"],
            "switch_id": switch_id,
            "brightness_id": brightness_id,
            "ip": hub.ip,
            "token": hub.token
        }
        lights.append(device_info)

    async_add_entities(LightClass(light) for light in lights)


    
#
# LIGHT
#    
class LightClass(LightEntity):

    # INIT
    def __init__(self, light) -> None:
        """Initialize a Light."""
        self._light = light
        self._name = light["name"]
        self._device_id = light["device_id"]
        self._switch_id = light["switch_id"]
        self._brightness_id = light["brightness_id"]
        self._token = light["token"]
        self._ip = light["ip"]
        self._switch = False
        self._brightness = 0
        
        self._attr_unique_id = f"{self._device_id}"
        self._attr_name = self._name

        # Set supported color modes
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        if self._brightness_id is not None:
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
        
        # Initialize color mode
        self._attr_color_mode = ColorMode.ONOFF


    # GET ON/OFF         
    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._switch
        
        
    # GET BRIGHTNESS
    @property
    def brightness(self):
        """Return the brightness of the light."""
        return self._brightness


    # SET ON
    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on."""
        self._switch = True
        
        if ATTR_BRIGHTNESS in kwargs:
            """turn on by setting brightness"""
            self._brightness  = int(kwargs.get(ATTR_BRIGHTNESS,255))
            self._attr_color_mode = ColorMode.BRIGHTNESS
            url = f'https://{self._ip}/api/junghome/functions/{self._device_id}/datapoints/{self._brightness_id}'
            body = {
                "data": [{
                            "key": "brightness",
                            "value": str(int((self._brightness / 255) * 100))
                        }]
            }
            response = await junghome.http_patch_request(url, self._token, body)
            if response is None: print("failed to turn on light.")
        else:
            """turn on by switching"""
            self._attr_color_mode = ColorMode.ONOFF
            url = f'https://{self._ip}/api/junghome/functions/{self._device_id}/datapoints/{self._switch_id}'
            body = {
                "data": [{
                            "key": "switch",
                            "value": "1"
                        }]
            }
            response = await junghome.http_patch_request(url, self._token, body)
            if response is None: print("failed to turn off light.")
        
        
    # SET OFF    
    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        self._switch = False
        self._attr_color_mode = ColorMode.ONOFF
        self._brightness = 0
        
        url = f'https://{self._ip}/api/junghome/functions/{self._device_id}/datapoints/{self._switch_id}'
        body = {
            "data": [{
                        "key": "switch",
                        "value": "0"
                    }]
        }
        response = await junghome.http_patch_request(url, self._token, body)
        if response is None: print("failed to turn off light.")


    # GET STATE
    async def async_update(self) -> None:
        """Fetch new state data for this light.
        This is the only method that should fetch new data for Home Assistant.
        """
        
        url = f'https://{self._ip}/api/junghome/functions/{self._device_id}/datapoints/{self._switch_id}'
        headers = {
            'accept': 'application/json',
            'token': self._token
        }
        
        response = await junghome.http_get_request(url, self._token)
        if response is None: 
            print("failed get state of light.")
            return None
        

        switch_value_str = response['values'][0]['value']
        switch_value = bool(int(switch_value_str))
        
        self._switch = switch_value
        self._brightness = self._brightness


