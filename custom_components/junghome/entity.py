from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER


class JunghomeDeviceEntity(CoordinatorEntity):
    """Shared base for device-backed Jung Home entities."""

    _device_id: str
    _device_model = "Unknown"

    def _get_device(self) -> dict:
        """Return current device payload from coordinator."""
        return self.coordinator.get_device_by_id(self._device_id) or {}

    def _sync_label_and_area(self) -> None:
        """Update entity label and apply area from coordinator data."""
        device = self._get_device()
        label = device.get("label")
        if label and label != self._attr_name:
            self._attr_name = label
        self.coordinator.apply_device_area(device)

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to Home Assistant."""
        await super().async_added_to_hass()
        self.coordinator.apply_device_area(self._get_device())

    def _build_device_info(self, model: str | None = None) -> DeviceInfo:
        """Build common DeviceInfo payload."""
        device = self._get_device()
        device_name = device.get("label") or self._attr_name
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=device_name,
            model=model or self._device_model,
            manufacturer=MANUFACTURER,
            suggested_area=device.get("suggested_area"),
        )

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        device = self.coordinator.get_device_by_id(self._device_id)
        if device is None:
            return False
        return device.get("available", True)

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes."""
        group_names = self._get_device().get("group_names", [])
        return {"groups": group_names} if group_names else {}
