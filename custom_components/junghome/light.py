"""Platform for light integration."""
from __future__ import annotations
import logging

from homeassistant.components.light import (ATTR_BRIGHTNESS, LightEntity, ColorMode)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

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
    """Set up Jung Home lights from a config entry."""
    
    # The coordinator is loaded from entry runtime_data that was set by __init__.py
    coordinator = config_entry.runtime_data
    _LOGGER.info("Initialize Jung Home lights from coordinator")
    
    # Get devices from coordinator data
    if coordinator.data is None or "devices" not in coordinator.data:
        _LOGGER.warning("No device data available from coordinator")
        return
        
    devices = coordinator.data["devices"]
    
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
        
        # Create light entity
        lights.append(JunghomeLight(coordinator, device, switch_id, brightness_id))

    async_add_entities(lights)


    
#
# LIGHT
#    
class JunghomeLight(CoordinatorEntity, LightEntity):
    """Jung Home light entity."""

    def __init__(self, coordinator, device, switch_id, brightness_id) -> None:
        """Initialize a Jung Home Light."""
        super().__init__(coordinator)
        
        self._device = device
        self._device_id = device["id"]
        self._switch_id = switch_id
        self._brightness_id = brightness_id
        self._switch = False
        self._brightness = 0
        
        self._attr_unique_id = f"{self._device_id}"
        self._attr_name = device["label"]

        # Set supported color modes
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        if self._brightness_id is not None:
            self._attr_supported_color_modes.add(ColorMode.BRIGHTNESS)
        
        # Initialize color mode
        self._attr_color_mode = ColorMode.ONOFF


    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=self._attr_name,
            model="Light",
            manufacturer=MANUFACTURER,
        )


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
            url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._brightness_id}'
            body = {
                "data": [{
                            "key": "brightness",
                            "value": str(int((self._brightness / 255) * 100))
                        }]
            }
            response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
            if response is None: print("failed to turn on light.")
        else:
            """turn on by switching"""
            self._attr_color_mode = ColorMode.ONOFF
            url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._switch_id}'
            body = {
                "data": [{
                            "key": "switch",
                            "value": "1"
                        }]
            }
            response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
            if response is None: print("failed to turn off light.")
        
        
    # SET OFF    
    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        self._switch = False
        self._attr_color_mode = ColorMode.ONOFF
        self._brightness = 0
        
        url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._switch_id}'
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
        
        url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._switch_id}'
        
        response = await JunghomeGateway.http_get_request(url, self.coordinator.token)
        if response is None: 
            print("failed get state of light.")
            return None
        

        switch_value_str = response['values'][0]['value']
        switch_value = bool(int(switch_value_str))
        
        self._switch = switch_value
        self._brightness = self._brightness


