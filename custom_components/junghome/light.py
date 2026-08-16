"""Platform for light integration."""
from __future__ import annotations
import logging

from homeassistant.components.light import (ATTR_BRIGHTNESS, LightEntity, ColorMode)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JunghomeConfigEntry
from .const import ROCKER_LED_DATAPOINT, ROCKER_SWITCH_TYPES
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
    """Set up Jung Home lights from a config entry."""
    
    # The coordinator is loaded from entry runtime_data that was set by __init__.py
    coordinator = config_entry.runtime_data
    _LOGGER.info("Initialize Jung Home lights from coordinator")
    
    # Register callback for dynamic device addition
    async def add_new_lights(devices):
        """Add new light devices dynamically."""
        lights = []
        for device in devices:
            # Rocker switches expose the status LED in their face as a light
            if device["type"] in ROCKER_SWITCH_TYPES:
                led_id = get_datapoint_id(device, ROCKER_LED_DATAPOINT)
                if led_id is not None:
                    lights.append(JunghomeRockerLed(coordinator, device, led_id))
                continue

            # skip non-light devices
            light_types = ["OnOff", "DimmerLight", "ColorLight"]
            if device["type"] not in light_types:
                continue

            switch_id = get_datapoint_id(device, "switch")
                
            # Skip no switch datapoint
            if switch_id is None:
                continue  
                
            brightness_id = get_datapoint_id(device, "brightness")
            
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
class JunghomeLight(JunghomeDeviceEntity, LightEntity):
    """Jung Home light entity."""

    def __init__(self, coordinator, device, switch_id, brightness_id) -> None:
        """Initialize a Jung Home Light."""
        super().__init__(coordinator)
        
        self._device_id = device["id"]
        self._switch_id = switch_id
        self._brightness_id = brightness_id
        
        # Per JUNG HOME documentation, device_id is unique across installations and device resets.
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
        self._sync_label_and_area()
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return device info."""
        return self._build_device_info("Light")


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


#
# ROCKER SWITCH STATUS LED
#
class JunghomeRockerLed(JunghomeDeviceEntity, LightEntity):
    """Status LED built into the face of a rocker switch.

    On/off only - the gateway exposes the LED as a plain boolean datapoint with
    no brightness or colour.
    """

    _attr_color_mode = ColorMode.ONOFF
    _attr_supported_color_modes = {ColorMode.ONOFF}

    def __init__(self, coordinator, device, led_id: str) -> None:
        """Initialize a Jung Home rocker status LED."""
        super().__init__(coordinator)

        self._device_id = device["id"]
        self._led_id = led_id
        self._attr_unique_id = f"{self._device_id}_{led_id}"
        self._attr_name = f"{device['label']} LED"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sync_label_and_area()
        label = self._get_device().get("label")
        if label:
            self._attr_name = f"{label} LED"
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return device info."""
        return self._build_device_info("Rocker Switch")

    @property
    def is_on(self) -> bool:
        """Return true if the status LED is lit."""
        return bool(self._get_device().get("states", {}).get(ROCKER_LED_DATAPOINT, False))

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the status LED on."""
        await self._async_set_led("1")

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the status LED off."""
        await self._async_set_led("0")

    async def _async_set_led(self, value: str) -> None:
        """Write the status LED datapoint."""
        url = f'https://{self.coordinator.ip}/api/junghome/functions/{self._device_id}/datapoints/{self._led_id}'
        body = {
            "data": [{
                "key": ROCKER_LED_DATAPOINT,
                "value": value
            }]
        }
        response = await JunghomeGateway.http_patch_request(url, self.coordinator.token, body)
        if response is None:
            _LOGGER.error("Failed to set status LED for rocker %s", self._device_id)
