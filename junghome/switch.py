"""Platform for switch integration."""
import logging
from homeassistant.components.switch import SwitchEntity, SwitchDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback


from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""
    # token = hass.data[DOMAIN]["token"]

    # You can use the token to authenticate and get your switch devices
    # ...

    # add entities
    async_add_entities([AwesomeSwitch("Switch 1"), AwesomeSwitch("Switch 2")])


class AwesomeSwitch(SwitchEntity):
    """Representation of a switch."""

    def __init__(self, name) -> None:
        self._name = name
        self._state = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_on(self) -> bool:
        return self._state

    async def async_turn_on(self, **kwargs) -> None:
        self._state = True
        print("on")
        self.schedule_update_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._state = False
        print("off")
        self.schedule_update_ha_state()
