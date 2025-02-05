from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform
from . import hub

# List of platforms to support. 
# each should match .py file (e.g. <cover.py> and <sensor.py>)
PLATFORMS = [Platform.COVER]
type HubConfigEntry = ConfigEntry[hub.Hub]

async def async_setup_entry(hass: HomeAssistant, entry: HubConfigEntry) -> bool:
    # Store an instance of the "connecting" class that does the work of speaking
    # with your actual devices.
    entry.runtime_data = hub.Hub(hass, entry.data["ip"], entry.data["token"])

    # This creates each HA object for each platform your device requires.
    # It's done by calling the `async_setup_entry` function in each platform module.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    return unload_ok
