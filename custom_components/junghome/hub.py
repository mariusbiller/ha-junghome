from __future__ import annotations
import asyncio
import logging

from homeassistant.core import HomeAssistant
from .junghome_client import JunghomeGateway

_LOGGER = logging.getLogger(__name__)

class Hub:
    """Jung Home Hub representation."""
    
    def __init__(self, hass: HomeAssistant, ip: str, token: str) -> None:
        """Initialize the hub."""
        self.ip = ip
        self.token = token
        self._hass = hass
        self._name = "JUNG HOME Gateway"
        self._id = ip.lower()
        self.online = False

    async def async_initialize(self) -> None:
        """Initialize the hub."""
        self.online = await self.test_connection()

    @property
    def hub_id(self) -> str:
        """Return the hub ID."""
        return self._id

    async def test_connection(self) -> bool:
        """Test connection to the Jung Home hub."""
        _LOGGER.debug("Testing connection to Jung Home hub at %s", self.ip)

        try:
            # Test actual connectivity with a timeout
            devices = await asyncio.wait_for(
                JunghomeGateway.request_devices(self.ip, self.token),
                timeout=10.0
            )
            
            if devices is None:
                _LOGGER.warning("Connection test failed: No response from hub at %s", self.ip)
                return False
                
            _LOGGER.info("Connection to Jung Home hub at %s is OK", self.ip)
            return True
            
        except asyncio.TimeoutError:
            _LOGGER.warning("Connection test failed: Timeout connecting to hub at %s", self.ip)
            return False
        except Exception as err:
            _LOGGER.warning("Connection test failed: %s", err)
            return False
        
