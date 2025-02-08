from __future__ import annotations
from homeassistant.core import HomeAssistant
from .junghome_client import JunghomeGateway as junghome
import logging
_LOGGER = logging.getLogger(__name__)

#
# HUB
#
class Hub:
    
    """Init hub."""
    def __init__(self, hass: HomeAssistant, ip: str, token: str) -> None:
        self.ip = ip
        self.token = token
        self._hass = hass
        self._name = "JUNG HOME Gateway"
        self._id = ip.lower()
        self.online = False

    async def async_initialize(self) -> None:
        self.online = True

    @property
    def hub_id(self) -> str:
        return self._id

    async def test_connection(self) -> bool:
        _LOGGER.info("Testing connection to the hub...")

        # Dummy validation logic for the token
        if self.token == "invalid_token":
            _LOGGER.warning("Connection test failed: Invalid token.")
            return False

        _LOGGER.info("Connection to the hub is OK.")
        return True
        
