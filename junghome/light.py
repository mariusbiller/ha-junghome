"""Platform for light integration."""
from __future__ import annotations

import logging
import junghome_client as junghome
import voluptuous as vol

# Import the device class from the component that you want to support
import homeassistant.helpers.config_validation as cv
from homeassistant.components.light import (ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, PLATFORM_SCHEMA, LightEntity, ColorMode)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
_LOGGER = logging.getLogger(__name__)

# Validation of the user's configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_USERNAME, default='admin'): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
})


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the Light platform."""
    # Assign configuration variables
    host = config[CONF_HOST]
    username = config[CONF_USERNAME]
    password = config.get(CONF_PASSWORD)

    # get jung home devices
    devices = junghome.request_devices(host, password)

    lights = []
    for device in devices:
    
        # skip non-light devices 
        light_types = ["OnOff", "DimmerLight", "ColorLight"] 
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
            "token": password
        }
        lights.append(device_info)

    add_entities(LightClass(light) for light in lights)


    
    
class LightClass(LightEntity):

    def __init__(self, light) -> None:
        """Initialize a Light."""
        self._light = light
        self._name = light["name"]
        self._device_id = light["device_id"]
        self._switch_id = light["switch_id"]
        self._brightness_id = light["brightness_id"]
        self._token = light["token"]
        self._switch = False
        self._brightness = 0

        """set supported mode"""
        supported_color_modes = {ColorMode.ONOFF}
        if self._brightness_id is not None:
            supported_color_modes.add(ColorMode.BRIGHTNESS)
        self._attr_supported_color_modes = supported_color_modes

    @property
    def name(self) -> str:
        """Return the display name of this light."""
        return self._name

    @property
    def unique_id(self) -> str | None:
        return self._light["device_id"]
        
    @property
    def brightness(self):
        """Return the brightness of the light.

        This method is optional. Removing it indicates to Home Assistant
        that brightness is not supported for this light.
        """
        return self._brightness

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        return self._switch

    def turn_on(self, **kwargs: Any) -> None:
        #self._light.turn_on()
        self._switch = True
        self._brightness  = int(kwargs.get(ATTR_BRIGHTNESS,255))
        
        url = f'https://junghome.local/api/junghome/functions/{self._device_id}/datapoints/{self._brightness_id}'
        headers = {
            'accept': 'application/json',
            'token': self._token,
            'Content-Type': 'application/json'
        }
        data = {
            "data": [
                {
                    "key": "brightness",
                    "value": str(int((self._brightness / 255) * 100))
                }
            ]
        }
        
        try:
            response = requests.patch(url, headers=headers, json=data, verify=False)
            response.raise_for_status()
            print("Light turned on successfully.")
        except requests.exceptions.RequestException as e:
            print(f"Failed to turn on light: {e}")

    def turn_off(self, **kwargs: Any) -> None:
        """Instruct the light to turn off."""
        self._brightness = 0
        #self._light.turn_off()
        self._switch = False
        
        url = f'https://junghome.local/api/junghome/functions/{self._device_id}/datapoints/{self._switch_id}'
        headers = {
            'accept': 'application/json',
            'token': self._token,
            'Content-Type': 'application/json'
        }
        data = {
            "data": [
                {
                    "key": "switch",
                    "value": "0"
                }
            ]
        }
        
        try:
            response = requests.patch(url, headers=headers, json=data, verify=False)
            response.raise_for_status()
            print("Light turned on successfully.")
        except requests.exceptions.RequestException as e:
            print(f"Failed to turn on light: {e}")

    def update(self) -> None:
        """Fetch new state data for this light.

        This is the only method that should fetch new data for Home Assistant.
        """
        url = f'https://junghome.local/api/junghome/functions/{self._device_id}/datapoints/{self._switch_id}'
        headers = {
            'accept': 'application/json',
            'token': self._token
        }
        
        try:
            response = requests.get(url, headers=headers, verify=False)
            response.raise_for_status()
            data = response.json()
            switch_value_str = data['values'][0]['value']
            switch_value = bool(int(switch_value_str))
            self._switch = switch_value
        except requests.exceptions.RequestException as e:
            print(f"Failed to get switch state: {e}")
            return None


        self._brightness = self._brightness

