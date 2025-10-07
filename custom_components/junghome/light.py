"""Platform for light integration."""
from __future__ import annotations
import logging

from homeassistant.components.light import (ATTR_BRIGHTNESS, LightEntity, ColorMode)
from homeassistant.core import HomeAssistant, callback
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
    
    # Register callback for dynamic device addition
    async def add_new_lights(devices):
        """Add new light devices dynamically."""
        lights = []
        light_types = {"OnOff", "DimmerLight", "ColorLight"}
        for device in devices:
            # skip non-light devices
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
        
        if lights:
            _LOGGER.info("Adding %d new light entities", len(lights))
            async_add_entities(lights)
    
    coordinator.register_entity_callback("light", add_new_lights)
    
    # Get initial devices from coordinator data
    if coordinator.data is None or "devices" not in coordinator.data:
        _LOGGER.warning("No device data available from coordinator")
        return
        
    devices = coordinator.data["devices"]
    
    # add light devices
    await add_new_lights(devices)


    
#
# LIGHT
#    
class JunghomeLight(CoordinatorEntity, LightEntity):
    """Jung Home light entity."""

    def __init__(self, coordinator, device, switch_id, brightness_id) -> None:
        """Initialize a Jung Home Light."""
        super().__init__(coordinator)
        
        self._device_id = device["id"]
        self._switch_id = switch_id
        self._brightness_id = brightness_id
        
        self._attr_unique_id = f"{self._device_id}"
        self._attr_name = device["label"]

        # Set supported color modes based on device type
        if device["type"] in ["DimmerLight", "ColorLight"] and self._brightness_id is not None:
            self._attr_supported_color_modes = {ColorMode.BRIGHTNESS}
            self._attr_color_mode = ColorMode.BRIGHTNESS
        else:
            self._attr_supported_color_modes = {ColorMode.ONOFF}
            self._attr_color_mode = ColorMode.ONOFF

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
            model="Light",
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
        """Return true if light is on."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device:
            return device.get("is_on", False)
        return False
        
        
    # GET BRIGHTNESS
    @property
    def brightness(self):
        """Return the brightness of the light."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device:
            return device.get("brightness", 0)
        return 0


    # SET ON
    async def async_turn_on(self, **kwargs) -> None:
        """Turn the light on."""
        # If brightness is specified and device supports it, use brightness control
        if (ATTR_BRIGHTNESS in kwargs and 
            self._brightness_id is not None and 
            self._attr_color_mode == ColorMode.BRIGHTNESS):
            
            brightness = int(kwargs.get(ATTR_BRIGHTNESS, 255))
            brightness_percent = int((brightness / 255) * 100)
            url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._brightness_id}'
            body = {
                "data": [{
                    "key": "brightness",
                    "value": str(brightness_percent)
                }]
            }
            response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
            if response is None: 
                _LOGGER.error("Failed to set brightness for light %s", self._device_id)
        else:
            # Use switch for simple turn on
            url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._switch_id}'
            body = {
                "data": [{
                    "key": "switch",
                    "value": "1"
                }]
            }
            response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
            if response is None: 
                _LOGGER.error("Failed to turn on light %s", self._device_id)
        
        
    # SET OFF    
    async def async_turn_off(self, **kwargs) -> None:
        """Turn the light off."""
        # Always use switch to turn off
        url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._switch_id}'
        body = {
            "data": [{
                "key": "switch",
                "value": "0"
            }]
        }
        response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
        if response is None: 
            _LOGGER.error("Failed to turn off light %s", self._device_id)


