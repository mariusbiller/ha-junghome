from __future__ import annotations
import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from .const import CONF_IP_ADDRESS, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .junghome_client import JunghomeGateway

_LOGGER = logging.getLogger(__name__)

class JunghomeCoordinator(DataUpdateCoordinator):
    """Jung Home data update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.entry = entry
        self.ip = entry.data[CONF_IP_ADDRESS]
        self.token = entry.data[CONF_TOKEN]
        self._gateway = JunghomeGateway(self.ip, self.token)
        self._functions = {}
        self._groups = {}
        self._scenes = {}
        
        # Store callbacks for dynamic entity management
        self._entity_callbacks = {
            "cover": [],
            "light": [],
            "sensor": [],
            "binary_sensor": []
        }
        
        # Track when device changes are expected
        self._expecting_device_changes = False

        super().__init__(
            hass,
            _LOGGER,
            name="Jung Home",
            update_interval=None,  # No polling, using WebSocket
        )

    async def _async_update_data(self) -> dict:
        """Return current data from WebSocket connection."""
        if not self._gateway.is_connected:
            raise UpdateFailed("WebSocket not connected")
            
        # Convert functions to devices format for compatibility
        devices = []
        for func_id, func_data in self._functions.items():
            device = self._convert_function_to_device(func_data)
            devices.append(device)
            
        return {
            "devices": devices,
            "functions": self._functions,
            "groups": self._groups,
            "scenes": self._scenes
        }

    async def async_setup(self) -> None:
        """Set up the coordinator and start WebSocket connection."""
        # Start WebSocket connection
        await self._gateway.connect_websocket(self._handle_websocket_data)
        
        # Wait a moment for initial WebSocket data
        await asyncio.sleep(2)
        
        # If no WebSocket data received, fall back to HTTP for initial setup
        if not self._functions:
            _LOGGER.info("No initial WebSocket data, falling back to HTTP fetch")
            try:
                devices = await asyncio.wait_for(
                    JunghomeGateway.request_devices(self.ip, self.token),
                    timeout=30.0
                )
                if devices:
                    for device in devices:
                        self._functions[device["id"]] = device
                    _LOGGER.info("Initial data loaded via HTTP: %d devices", len(devices))
            except Exception as err:
                _LOGGER.warning("Failed to get initial device data via HTTP: %s", err)
                raise

    async def async_shutdown(self) -> None:
        """Shutdown the coordinator and disconnect WebSocket."""
        await self._gateway.disconnect_websocket()

    async def _handle_websocket_data(self, data_type: str, data: dict) -> None:
        """Handle incoming WebSocket data."""
        if data_type == "functions":
            # Only check for device changes when we're expecting them or on initial load
            should_check_changes = self._expecting_device_changes or not self._functions
            
            if should_check_changes:
                old_functions = self._functions.copy()
                self._functions = data
                await self._handle_device_changes(old_functions, self._functions)
                self._expecting_device_changes = False
            else:
                # Fast path - just update functions data
                self._functions = data
            
            self.async_set_updated_data(await self._async_update_data())
            
        elif data_type == "groups":
            self._groups = data
            
        elif data_type == "scenes":
            self._scenes = data
            
        elif data_type == "datapoint":
            # Fast path for individual datapoint updates
            await self._handle_datapoint_update(data)
            
        elif data_type == "devices-new":
            _LOGGER.info("New devices detected: %s", data)
            self._expecting_device_changes = True
            
        elif data_type == "devices-deleted":
            _LOGGER.info("Devices deleted: %s", data)
            self._expecting_device_changes = True

    async def _handle_device_changes(self, old_functions: dict, new_functions: dict) -> None:
        """Handle device additions and deletions."""
        old_device_ids = set(old_functions.keys())
        new_device_ids = set(new_functions.keys())
        
        # Early exit if no changes
        if old_device_ids == new_device_ids:
            _LOGGER.debug("No device changes detected")
            return
        
        # Find new devices
        added_devices = new_device_ids - old_device_ids
        if added_devices:
            _LOGGER.info("Adding new devices: %s", added_devices)
            await self._add_new_devices(added_devices, new_functions)
        
        # Find deleted devices  
        deleted_devices = old_device_ids - new_device_ids
        if deleted_devices:
            _LOGGER.info("Removing deleted devices: %s", deleted_devices)
            await self._remove_deleted_devices(deleted_devices)

    async def _add_new_devices(self, device_ids: set, functions: dict) -> None:
        """Add new devices to existing platforms."""
        from homeassistant.helpers import entity_registry as er
        
        # Get new devices data
        new_devices = []
        for device_id in device_ids:
            if device_id in functions:
                device_data = functions[device_id]
                converted_device = self._convert_function_to_device(device_data)
                new_devices.append(converted_device)
        
        # Add new entities to each platform
        for platform_type, callbacks in self._entity_callbacks.items():
            platform_devices = []
            
            for device in new_devices:
                if self._device_belongs_to_platform(device, platform_type):
                    platform_devices.append(device)
            
            if platform_devices and callbacks:
                # Call the platform's entity creation callback
                for callback in callbacks:
                    await callback(platform_devices)

    async def _remove_deleted_devices(self, device_ids: set) -> None:
        """Remove deleted devices from entity registry."""
        from homeassistant.helpers import entity_registry as er
        
        entity_registry = er.async_get(self.hass)
        
        for device_id in device_ids:
            # Find and remove entities for this device
            entities_to_remove = []
            for entity_id, entry in entity_registry.entities.items():
                if (entry.config_entry_id == self.entry.entry_id and 
                    entry.unique_id == device_id):
                    entities_to_remove.append(entity_id)
            
            for entity_id in entities_to_remove:
                _LOGGER.info("Removing entity: %s for deleted device: %s", entity_id, device_id)
                entity_registry.async_remove(entity_id)

    def _device_belongs_to_platform(self, device: dict, platform_type: str) -> bool:
        """Check if device belongs to a specific platform."""
        device_type = device.get("type")
        
        if platform_type == "cover":
            return device_type in ["Position", "PositionAndAngle"]
        elif platform_type == "light":
            return device_type in ["OnOff", "DimmerLight", "ColorLight", "Socket"]
        elif platform_type in ["sensor", "binary_sensor"]:
            # These are handled by hub config, not device functions
            return False
        
        return False

    def register_entity_callback(self, platform_type: str, callback) -> None:
        """Register a callback for dynamic entity creation."""
        if platform_type in self._entity_callbacks:
            self._entity_callbacks[platform_type].append(callback)

    async def _handle_datapoint_update(self, datapoint_data: dict) -> None:
        """Handle real-time datapoint updates."""
        datapoint_id = datapoint_data.get("id")
        datapoint_type = datapoint_data.get("type")
        values = datapoint_data.get("values", [])
        
        # Find the function that contains this datapoint
        for func_id, func_data in self._functions.items():
            for dp in func_data.get("datapoints", []):
                if dp.get("id") == datapoint_id:
                    # Update the datapoint values
                    dp["values"] = values
                    
                    # Update device state based on datapoint type
                    self._update_device_state_from_datapoint(func_data, datapoint_type, values)
                    
                    # Trigger update to entities
                    self.async_set_updated_data(await self._async_update_data())
                    return

    def _update_device_state_from_datapoint(self, device: dict, datapoint_type: str, values: list) -> None:
        """Update device state based on datapoint values."""
        if not values:
            return
            
        device_type = device.get("type")
        
        # Check if any value is NaN to mark device as unavailable
        has_nan = any(item.get("value") == "NaN" for item in values)
        
        if datapoint_type == "level" and device_type in ["Position", "PositionAndAngle"]:
            if has_nan:
                device["available"] = False
            else:
                device["available"] = True
                # Process all values in the level datapoint (level and level_move)
                for value_item in values:
                    key = value_item.get("key")
                    value = value_item.get("value")
                    if value is None:
                        continue
                        
                    try:
                        if key == "level":
                            level_value = int(float(value))
                            device["current_position"] = 100 - level_value  # Jung Home uses inverted scale
                        elif key == "level_move":
                            # Store movement state for is_opening/is_closing properties
                            device["level_move"] = int(float(value))
                    except (ValueError, TypeError):
                        # Skip invalid values
                        continue
            
        elif datapoint_type == "switch" and device_type in ["OnOff", "DimmerLight", "ColorLight", "Socket"]:
            value = values[0].get("value") if values else None
            if value == "NaN":
                device["available"] = False
            elif value is not None:
                device["available"] = True
                try:
                    device["is_on"] = bool(int(float(value)))
                except (ValueError, TypeError):
                    # Skip invalid values
                    pass
            
        elif datapoint_type == "brightness" and device_type in ["DimmerLight", "ColorLight"]:
            value = values[0].get("value") if values else None
            if value == "NaN":
                device["available"] = False
            elif value is not None:
                device["available"] = True
                try:
                    brightness_value = int(float(value))
                    device["brightness"] = int((brightness_value / 100) * 255)  # Convert to HA scale
                except (ValueError, TypeError):
                    # Skip invalid values
                    pass

    def _convert_function_to_device(self, func_data: dict) -> dict:
        """Convert function data to device format for compatibility."""
        device = func_data.copy()
        device_type = device.get("type")
        
        # Set default states based on current datapoint values
        device["available"] = True  # Default to available
        
        if device_type in ["Position", "PositionAndAngle"]:
            level_datapoint = self._find_datapoint(device, "level")
            if level_datapoint and level_datapoint.get("values"):
                # Check if any level value is NaN
                has_nan = any(item.get("value") == "NaN" for item in level_datapoint["values"])
                if has_nan:
                    device["available"] = False
                else:
                    # Process all values in level datapoint
                    for value_item in level_datapoint["values"]:
                        key = value_item.get("key")
                        value = value_item.get("value", 0)
                        
                        if value is None:
                            continue
                            
                        try:
                            if key == "level":
                                device["current_position"] = 100 - int(float(value))
                            elif key == "level_move":
                                device["level_move"] = int(float(value))
                        except (ValueError, TypeError):
                            continue
                        
                # Set defaults if not found
                if "current_position" not in device:
                    device["current_position"] = 50
                if "level_move" not in device:
                    device["level_move"] = 0
            else:
                device["current_position"] = 50
                device["level_move"] = 0
                
        elif device_type in ["OnOff", "DimmerLight", "ColorLight", "Socket"]:
            switch_datapoint = self._find_datapoint(device, "switch")
            if switch_datapoint and switch_datapoint.get("values"):
                value = switch_datapoint["values"][0].get("value", 0)
                if value == "NaN":
                    device["available"] = False
                elif value is not None:
                    try:
                        device["is_on"] = bool(int(float(value)))
                    except (ValueError, TypeError):
                        device["is_on"] = False
                else:
                    device["is_on"] = False
            else:
                device["is_on"] = False
                
            if device_type in ["DimmerLight", "ColorLight"]:
                brightness_datapoint = self._find_datapoint(device, "brightness")
                if brightness_datapoint and brightness_datapoint.get("values"):
                    value = brightness_datapoint["values"][0].get("value", 0)
                    if value == "NaN":
                        device["available"] = False
                    elif value is not None:
                        try:
                            brightness_value = int(float(value))
                            device["brightness"] = int((brightness_value / 100) * 255)
                        except (ValueError, TypeError):
                            device["brightness"] = 255 if device.get("is_on") else 0
                    else:
                        device["brightness"] = 255 if device.get("is_on") else 0
                else:
                    device["brightness"] = 255 if device.get("is_on") else 0
                    
        return device

    def _find_datapoint(self, device: dict, datapoint_type: str) -> dict | None:
        """Find a datapoint of specific type in device."""
        for datapoint in device.get("datapoints", []):
            if datapoint.get("type") == datapoint_type:
                return datapoint
        return None

    @property
    def devices(self) -> list | None:
        """Return the devices data."""
        if self.data and "devices" in self.data:
            return self.data["devices"]
        return None

    @property
    def functions(self) -> dict:
        """Return the functions data."""
        return self._functions

    @property  
    def groups(self) -> dict:
        """Return the groups data."""
        return self._groups

    @property
    def scenes(self) -> dict:
        """Return the scenes data."""
        return self._scenes

    def get_device_by_id(self, device_id: str) -> dict | None:
        """Get device data by device ID."""
        if self.data and "devices" in self.data:
            for device in self.data["devices"]:
                if device["id"] == device_id:
                    return device
        return None

    async def test_connection(self) -> bool:
        """Test connection to the Jung Home hub."""
        try:
            if self._gateway.is_connected:
                return True
            
            # Fallback to HTTP test if WebSocket not connected
            devices = await asyncio.wait_for(
                JunghomeGateway.request_devices(self.ip, self.token),
                timeout=30.0
            )
            return devices is not None
        except Exception as err:
            _LOGGER.debug("Connection test failed: %s", err)
            return False

    @property
    def is_websocket_connected(self) -> bool:
        """Return True if WebSocket is connected."""
        return self._gateway.is_connected