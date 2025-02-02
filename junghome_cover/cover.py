"""Platform for sensor integration."""
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
   
    """Add cover for passed config_entry in HA."""
    # The hub is loaded from the associated entry runtime data that was set in the
    # __init__.async_setup_entry function
    hub = config_entry.runtime_data
    _LOGGER.info(f"Initialize {hub.ip} WindowCovers from hub")
    
    # Get JUNG HOME devices
    devices = await junghome.request_devices(hub.ip, hub.token)

    if devices is None:
        _LOGGER.info("Failed to retrieve cover devices. API response was None.")
        hub.online = False
        return

    _LOGGER.debug(f"Devices response: {devices}")

    covers = []
    for device in devices:
         # skip non-cover devices 
        cover_types = ["Position", "PositionAndAngle"] 
        if device["type"] not in cover_types:
            continue
        
        # init and add add cover class
        covers.append(Roller(device.get("id"), device.get("label"), hub))
    
    # Add all entities to HA
    async_add_entities(HelloWorldCover(cover) for cover in covers)


#
# WINDOW COVER
#
class HelloWorldCover(CoverEntity):
    """Representation of a dummy Cover."""

    # Our dummy class is PUSH, so we tell HA that it should not be polled
    should_poll = False
    # The supported features of a cover are done using a bitmask. Using the constants
    # imported above, we can tell HA the features that are supported by this entity.
    # If the supported features were dynamic (ie: different depending on the external
    # device it connected to), then this should be function with an @property decorator.
    supported_features = CoverEntityFeature.SET_POSITION | CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(self, roller) -> None:
        """Initialize the sensor."""
        # Usual setup is done here. Callbacks are added in async_added_to_hass.
        self._roller = roller

        # A unique_id for this entity with in this domain. This means for example if you
        # have a sensor on this cover, you must ensure the value returned is unique,
        # which is done here by appending "_cover". For more information, see:
        # https://developers.home-assistant.io/docs/entity_registry_index/#unique-id-requirements
        # Note: This is NOT used to generate the user visible Entity ID used in automations.
        self._attr_unique_id = f"{self._roller.roller_id}_cover"

        # This is the name for this *entity*, the "name" attribute from "device_info"
        # is used as the device name for device screens in the UI. This name is used on
        # entity screens, and used to build the Entity ID that's used is automations etc.
        self._attr_name = self._roller.name

    async def async_added_to_hass(self) -> None:
        """Run when this Entity has been added to HA."""
        # Importantly for a push integration, the module that will be getting updates
        # needs to notify HA of changes. The dummy device has a registercallback
        # method, so to this we add the 'self.async_write_ha_state' method, to be
        # called where ever there are changes.
        # The call back registration is done once this entity is registered with HA
        # (rather than in the __init__)
        self._roller.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Entity being removed from hass."""
        # The opposite of async_added_to_hass. Remove any registered call backs here.
        self._roller.remove_callback(self.async_write_ha_state)

    # Information about the devices that is partially visible in the UI.
    # The most critical thing here is to give this entity a name so it is displayed
    # as a "device" in the HA UI. This name is used on the Devices overview table,
    # and the initial screen when the device is added (rather than the entity name
    # property below). You can then associate other Entities (eg: a battery
    # sensor) with this device, so it shows more like a unified element in the UI.
    # For example, an associated battery sensor will be displayed in the right most
    # column in the Configuration > Devices view for a device.
    # To associate an entity with this device, the device_info must also return an
    # identical "identifiers" attribute, but not return a name attribute.
    # See the sensors.py file for the corresponding example setup.
    # Additional meta data can also be returned here, including sw_version (displayed
    # as Firmware), model and manufacturer (displayed as <model> by <manufacturer>)
    # shown on the device info screen. The Manufacturer and model also have their
    # respective columns on the Devices overview table. Note: Many of these must be
    # set when the device is first added, and they are not always automatically
    # refreshed by HA from it's internal cache.
    # For more information see:
    # https://developers.home-assistant.io/docs/device_registry_index/#device-properties
    @property
    def device_info(self) -> DeviceInfo:
        """Information about this entity/device."""
        return {
            "identifiers": {(DOMAIN, self._roller.roller_id)},
            # If desired, the name for the device could be different to the entity
            "name": self.name,
            "sw_version": self._roller.firmware_version,
            "model": self._roller.model,
            "manufacturer": MANUFACTURER,
        }

    # This property is important to let HA know if this entity is online or not.
    # If an entity is offline (return False), the UI will refelect this.
    @property
    def available(self) -> bool:
        """Return True if roller and hub is available."""
        return self._roller.online and self._roller.hub.online

    # The following properties are how HA knows the current state of the device.
    # These must return a value from memory, not make a live query to the device/hub
    # etc when called (hence they are properties). For a push based integration,
    # HA is notified of changes via the async_write_ha_state call. See the __init__
    # method for hos this is implemented in this example.
    # The properties that are expected for a cover are based on the supported_features
    # property of the object. In the case of a cover, see the following for more
    # details: https://developers.home-assistant.io/docs/core/entity/cover/
    @property
    def current_cover_position(self):
        """Return the current position of the cover."""
        return self._roller.position

    @property
    def is_closed(self) -> bool:
        """Return if the cover is closed, same as position 0."""
        return self._roller.position == 0

    @property
    def is_closing(self) -> bool:
        """Return if the cover is closing or not."""
        return self._roller.moving < 0

    @property
    def is_opening(self) -> bool:
        """Return if the cover is opening or not."""
        return self._roller.moving > 0

    # These methods allow HA to tell the actual device what to do. In this case, move
    # the cover to the desired position, or open and close it all the way.
    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._roller.set_position(100)

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._roller.set_position(0)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._roller.set_position(kwargs[ATTR_POSITION])



#
# DUMMY WINDOW COVER
#
class Roller:
    """Dummy roller (device for HA) for Hello World example."""

    def __init__(self, rollerid: str, name: str, hub: Hub) -> None:
        """Init dummy roller."""
        self._id = rollerid
        self.hub = hub
        self.name = name
        self._callbacks = set()
        self._loop = asyncio.get_event_loop()
        self._target_position = 100
        self._current_position = 100
        self.moving = 0  # >0 is up, <0 is down

        # Some static information about this device
        self.firmware_version = f"0.0.{random.randint(1, 9)}"
        self.model = "WindowCover"

        _LOGGER.error(f"Initialized Roller: {self.name} with ID {self._id}")

    @property
    def roller_id(self) -> str:
        """Return ID for roller."""
        return self._id

    @property
    def position(self):
        """Return position for roller."""
        return self._current_position

    async def set_position(self, position: int) -> None:
        """
        Set dummy cover to the given position.

        State is announced a random number of seconds later.
        """
        _LOGGER.info(f"Setting position for Roller {self.name} to {position}")
        self._target_position = position

        # Update the moving status and broadcast the update
        self.moving = position - 50
        await self.publish_updates()

        self._loop.create_task(self.delayed_update())

    async def delayed_update(self) -> None:
        """Publish updates, with a random delay to emulate interaction with device."""
        await asyncio.sleep(random.randint(1, 10))
        self.moving = 0
        await self.publish_updates()

    def register_callback(self, callback: Callable[[], None]) -> None:
        """Register callback, called when Roller changes state."""
        self._callbacks.add(callback)
        _LOGGER.debug(f"Callback registered for Roller {self.name}")

    def remove_callback(self, callback: Callable[[], None]) -> None:
        """Remove previously registered callback."""
        self._callbacks.discard(callback)
        _LOGGER.debug(f"Callback removed for Roller {self.name}")

    async def publish_updates(self) -> None:
        """Schedule call all registered callbacks."""
        self._current_position = self._target_position
        _LOGGER.debug(f"Roller {self.name} updated position to {self._current_position}")
        for callback in self._callbacks:
            callback()

    @property
    def online(self) -> float:
        """Roller is online."""
        return random.random() > 0.1

    @property
    def battery_level(self) -> int:
        """Battery level as a percentage."""
        return random.randint(0, 100)

    @property
    def battery_voltage(self) -> float:
        """Return a random voltage roughly that of a 12v battery."""
        return round(random.random() * 3 + 10, 2)

    @property
    def illuminance(self) -> int:
        """Return a sample illuminance in lux."""
        return random.randint(0, 500)