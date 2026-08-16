"""Platform for event integration."""
from __future__ import annotations
import logging

from homeassistant.components.event import EventDeviceClass, EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import JunghomeConfigEntry
from .const import DOMAIN, ROCKER_DIRECTIONS, ROCKER_SWITCH_TYPES
from .datapoints import get_datapoint_id
from .entity import JunghomeDeviceEntity

_LOGGER = logging.getLogger(__name__)

EVENT_PRESS = "press"
EVENT_RELEASE = "release"


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JunghomeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jung Home rocker switch events from a config entry."""
    coordinator = config_entry.runtime_data
    registry = er.async_get(hass)
    _LOGGER.info("Initialize Jung Home rocker events from coordinator")

    async def add_new_events(devices):
        """Add event entities for new rocker switch devices dynamically."""
        events = []
        for device in devices:
            if device["type"] not in ROCKER_SWITCH_TYPES:
                continue

            for datapoint_type, label_suffix in ROCKER_DIRECTIONS.items():
                datapoint_id = get_datapoint_id(device, datapoint_type)
                if datapoint_id is None:
                    continue

                _remove_superseded_button(registry, device["id"], datapoint_id)

                events.append(
                    JunghomeRockerEvent(
                        coordinator,
                        device,
                        datapoint_id,
                        datapoint_type,
                        label_suffix,
                    )
                )

        if events:
            _LOGGER.info("Adding %d new rocker event entities", len(events))
            async_add_entities(events)

    coordinator.register_entity_callback("event", add_new_events)

    if coordinator.data is None or "devices" not in coordinator.data:
        _LOGGER.warning("No device data available from coordinator")
        return

    await add_new_events(coordinator.data["devices"])


def _remove_superseded_button(registry: er.EntityRegistry, device_id: str, datapoint_id: str) -> None:
    """Drop the button entity this direction used to be registered as.

    Rocker directions were button entities before the event platform existed.
    Home Assistant keeps registry entries for platforms that stop being set up,
    so without this the old buttons linger as unavailable forever. The unique_id
    is unchanged, only the domain moved, which makes the old row easy to find.
    """
    unique_id = f"{device_id}_{datapoint_id}"
    old_entity_id = registry.async_get_entity_id("button", DOMAIN, unique_id)
    if old_entity_id:
        _LOGGER.info("Removing button entity %s superseded by an event entity", old_entity_id)
        registry.async_remove(old_entity_id)


class JunghomeRockerEvent(JunghomeDeviceEntity, EventEntity):
    """Press and release events for one direction of a rocker switch.

    The gateway reports each direction as a request datapoint that goes to "1"
    on press and back to "0" on release, with no repeats while the key is held.
    Emitting both edges is what makes continuous-push effects such as
    hold-to-dim possible: an automation starts on "press" and stops on
    "release", using the time between them as the hold duration.
    """

    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = [EVENT_PRESS, EVENT_RELEASE]

    def __init__(
        self,
        coordinator,
        device,
        datapoint_id: str,
        datapoint_type: str,
        label_suffix: str,
    ) -> None:
        """Initialize a Jung Home rocker switch event entity."""
        super().__init__(coordinator)
        self._device_id = device["id"]
        self._datapoint_id = datapoint_id
        self._datapoint_type = datapoint_type
        self._label_suffix = label_suffix

        self._attr_unique_id = f"{self._device_id}_{self._datapoint_id}"
        self._attr_name = f"{device['label']} {self._label_suffix}"

        # Seed from current state so a key already held at startup does not
        # produce a phantom press on the first coordinator update.
        self._pressed = self._is_pressed(device)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sync_label_and_area()
        self._sync_rocker_label()

        # This runs on every coordinator refresh for every entity, including
        # unrelated devices, so only a change in level is an actual edge.
        device = self.coordinator.get_device_by_id(self._device_id)
        was_pressed, self._pressed = self._pressed, self._is_pressed(device)

        if self._pressed != was_pressed:
            self._trigger_event(EVENT_PRESS if self._pressed else EVENT_RELEASE)

        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return device info."""
        return self._build_device_info("Rocker Switch")

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        attributes = super().extra_state_attributes
        attributes["datapoint_id"] = self._datapoint_id
        attributes["datapoint_type"] = self._datapoint_type
        return attributes

    def _sync_rocker_label(self) -> None:
        """Re-append the direction suffix that _sync_label_and_area strips."""
        label = self._get_device().get("label")
        if label:
            self._attr_name = f"{label} {self._label_suffix}"

    def _is_pressed(self, device: dict | None) -> bool:
        """Return True while the rocker direction is held down."""
        if not device:
            return False
        return bool(device.get("states", {}).get(self._datapoint_type, False))
