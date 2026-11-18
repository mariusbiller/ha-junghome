"""Platform for JUNG HOME scenes."""
from __future__ import annotations

import logging
from urllib.parse import quote

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import JunghomeConfigEntry
from .junghome_client import JunghomeGateway

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JunghomeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jung Home scenes from a config entry."""
    coordinator = config_entry.runtime_data

    async def add_new_scenes(scenes):
        """Add new scene entities dynamically."""
        entities = [JunghomeScene(coordinator, scene["id"]) for scene in scenes]
        if entities:
            _LOGGER.info("Adding %d new scene entities", len(entities))
            async_add_entities(entities)

    coordinator.register_entity_callback("scene", add_new_scenes)
    await add_new_scenes(coordinator.scenes.values())


class JunghomeScene(CoordinatorEntity, Scene):
    """A scene whose actions are stored and executed by the gateway."""

    def __init__(self, coordinator, scene_id: str) -> None:
        super().__init__(coordinator)
        self._scene_id = scene_id
        self._attr_unique_id = coordinator.scene_unique_id(scene_id)

    @property
    def name(self) -> str:
        """Return the current gateway label."""
        return self.coordinator.scenes.get(self._scene_id, {}).get("label") or self._scene_id

    @property
    def available(self) -> bool:
        """Return whether the scene is still present on the gateway."""
        return super().available and self._scene_id in self.coordinator.scenes

    async def async_activate(self, **kwargs) -> None:
        """Activate the scene using the gateway's saved settings."""
        if self._scene_id not in self.coordinator.scenes:
            raise HomeAssistantError(f"JUNG HOME scene {self._scene_id} no longer exists")
        scene_id = quote(self._scene_id, safe="")
        url = f"https://{self.coordinator.ip}/api/junghome/scenes/{scene_id}"
        response = await JunghomeGateway.http_post_request(url, self.coordinator.token)
        if response is None:
            raise HomeAssistantError(f"Failed to activate JUNG HOME scene {self._scene_id}")
