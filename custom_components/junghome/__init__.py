from __future__ import annotations
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import JunghomeCoordinator
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# List of platforms to support. 
# each should match .py file (e.g. <cover.py> and <light.py>)
PLATFORMS = [
    Platform.LIGHT,
    Platform.COVER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
]
JunghomeConfigEntry = ConfigEntry[JunghomeCoordinator]

async def async_setup_entry(hass: HomeAssistant, entry: JunghomeConfigEntry) -> bool:
    """Set up JUNG HOME from a config entry."""
    coordinator = JunghomeCoordinator(hass, entry)
    
    try:
        # Set up WebSocket connection
        await coordinator.async_setup()
        
        # Test initial connection and raise ConfigEntryNotReady if it fails
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:
        _LOGGER.error("Failed to connect to JUNG HOME gateway at %s: %s", 
                     coordinator.ip, err)
        raise ConfigEntryNotReady(f"Unable to connect to JUNG HOME gateway at {coordinator.ip}") from err

    # Store coordinator in runtime_data
    entry.runtime_data = coordinator

    # Forward the setup to the platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    coordinator = entry.runtime_data
    if coordinator:
        await coordinator.async_shutdown()
        
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok
