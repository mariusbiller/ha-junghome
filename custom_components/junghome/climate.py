"""Climate-Plattform fuer JUNG HOME Raumthermostate.

Erweiterung der Integration ha-junghome von Marius Biller
(https://github.com/mariusbiller/ha-junghome).
Entwickelt von micthon mit Unterstuetzung von KI.
Hinweise zur Thermostat-Schnittstelle des Gateways stammen aus der
Dokumentation von ernetas/junghome (https://github.com/ernetas/junghome).

Ein JUNG-HOME-Raumthermostat ("type": "Thermostat") hat drei Datenpunkte:

- ``temperature_ctrl``: Solltemperatur in °C (Bereich 5..30, Schritt 0.5) und
  der Schluessel ``temperature_ctrl_preset``.
  Schreiben: nur ``frost`` / ``eco`` / ``comfort``.
  Lesen: das passende Preset oder ``""`` (= kein Preset passt). Das Gateway
  leitet das Preset selbst ab, indem es die Solltemperatur mit den drei im
  Thermostat hinterlegten Temperaturen vergleicht.
- ``quantity``: gemessene Raumtemperatur (Ist-Wert).
- ``switch``: wird bewusst NICHT ausgewertet. Trotz des Namens ist es kein
  Ein/Aus-Schalter, und die Messwerte zeigen, dass es auch nicht zuverlaessig
  "heizt gerade" bedeutet (alle Thermostate meldeten 1, obwohl der Raum
  deutlich ueber der Solltemperatur lag).

Das Thermostat laesst sich ueber das Gateway nicht ausschalten. Die Entitaet
steht deshalb dauerhaft auf "heizen"; der "Ausschalter" ist das Preset ``Frost``.

Preset-Erkennung: Die drei Preset-Temperaturen kennt nur das Thermostat selbst.
Die Entitaet merkt sich deshalb jedes Mal, wenn das Gateway ein Preset samt
Solltemperatur meldet (z. B. eco = 17 °C), welche Temperatur dazu gehoert, und
speichert das ueber Neustarts hinweg. Stellt man spaeter per +/- wieder genau
diese Temperatur ein, zeigt die Entitaet das Preset wieder an, auch wenn das
Gateway selbst kein Preset mitschickt.
"""
from __future__ import annotations

import logging
import math
from typing import Any

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    PRESET_COMFORT,
    PRESET_ECO,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import JunghomeConfigEntry
from .datapoints import get_datapoint_id
from .entity import JunghomeDeviceEntity
from .junghome_client import JunghomeGateway

_LOGGER = logging.getLogger(__name__)

MIN_TEMP = 5.0
MAX_TEMP = 30.0

# Zwei Temperaturen gelten als "gleich", wenn sie weniger als diesen Wert
# auseinanderliegen (die Schrittweite des Thermostats ist 0,5 °C).
TEMP_TOLERANCE = 0.25

# Name des Zusatz-Attributs, in dem die gelernten Preset-Temperaturen stehen.
ATTR_PRESET_TEMPERATURES = "preset_temperatures"

# "Frostschutz" gibt es in Home Assistant nicht als Standard-Preset. Der Name
# wird so angezeigt, wie er hier steht (in Automationen: preset_mode: Frost).
PRESET_FROST = "Frost"

# Home-Assistant-Preset -> Wert, den das Gateway beim Schreiben akzeptiert.
# Ein Preset "Ohne" gibt es absichtlich nicht: das Gateway lehnt es ab.
_HA_TO_DEVICE_PRESET = {
    PRESET_FROST: "frost",
    PRESET_ECO: "eco",
    PRESET_COMFORT: "comfort",
}

# Gateway-Wert -> Home-Assistant-Preset (nur die drei echten Presets).
_DEVICE_TO_HA_PRESET = {device: ha for ha, device in _HA_TO_DEVICE_PRESET.items()}


#
# Setup
#
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: JunghomeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Jung Home thermostats from a config entry."""

    # The coordinator is loaded from entry runtime_data that was set by __init__.py
    coordinator = config_entry.runtime_data
    _LOGGER.info("Initialize Jung Home thermostats from coordinator")

    # Register callback for dynamic device addition
    async def add_new_thermostats(devices):
        """Add new thermostat devices dynamically."""
        thermostats = []
        for device in devices:
            # skip non-thermostat devices
            if device["type"] != "Thermostat":
                continue

            ctrl_id = get_datapoint_id(device, "temperature_ctrl")

            # Skip thermostats without a setpoint datapoint
            if ctrl_id is None:
                continue

            thermostats.append(JunghomeThermostat(coordinator, device, ctrl_id))

        if thermostats:
            _LOGGER.info("Adding %d new thermostat entities", len(thermostats))
            async_add_entities(thermostats)

    coordinator.register_entity_callback("climate", add_new_thermostats)

    # Get initial devices from coordinator data
    if coordinator.data is None or "devices" not in coordinator.data:
        _LOGGER.warning("No device data available from coordinator")
        return

    devices = coordinator.data["devices"]

    # add thermostat devices
    await add_new_thermostats(devices)


#
# THERMOSTAT
#
class JunghomeThermostat(JunghomeDeviceEntity, ClimateEntity, RestoreEntity):
    """Jung Home room thermostat entity."""

    _device_model = "Thermostat"

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _attr_min_temp = MIN_TEMP
    _attr_max_temp = MAX_TEMP
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_hvac_mode = HVACMode.HEAT
    _attr_preset_modes = [PRESET_FROST, PRESET_ECO, PRESET_COMFORT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.PRESET_MODE
    )

    def __init__(self, coordinator, device, ctrl_id: str) -> None:
        """Initialize a Jung Home Thermostat."""
        super().__init__(coordinator)

        self._device_id = device["id"]
        self._ctrl_id = ctrl_id

        # Per JUNG HOME documentation, device_id is unique across installations and device resets.
        self._attr_unique_id = f"{self._device_id}"
        self._attr_name = device["label"]

        # Gelernte Preset-Temperaturen, z. B. {"eco": 17.0, "comfort": 22.0}
        self._preset_temps: dict[str, float] = {}

        # Sofort angezeigter Wert nach einem Befehl, bis das Gateway antwortet
        # (siehe _effective_state).
        self._optimistic: dict[str, Any] | None = None

    async def async_added_to_hass(self) -> None:
        """Restore learned preset temperatures after a restart."""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None:
            saved = last_state.attributes.get(ATTR_PRESET_TEMPERATURES)
            if isinstance(saved, dict):
                for name, temperature in saved.items():
                    number = self._to_float(temperature)
                    if name in _DEVICE_TO_HA_PRESET and number is not None:
                        self._preset_temps[name] = number

        # Was das Gateway jetzt gerade meldet, gilt vor dem gespeicherten Wert.
        self._learn_presets()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._sync_label_and_area()
        self._learn_presets()
        self.async_write_ha_state()

    @property
    def device_info(self):
        """Return device info."""
        return self._build_device_info("Thermostat")

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes, including the learned preset temperatures."""
        attributes = dict(super().extra_state_attributes or {})
        if self._preset_temps:
            attributes[ATTR_PRESET_TEMPERATURES] = dict(self._preset_temps)
        return attributes

    # ------------------------------------------------------------------
    # Hilfsfunktionen zum Lesen der Datenpunkte
    # ------------------------------------------------------------------
    def _read_value(self, datapoint_type: str, key: str) -> str | None:
        """Return the raw value of ``key`` inside the first datapoint of a type."""
        device = self._get_device()
        for datapoint in device.get("datapoints", []):
            if datapoint.get("type") != datapoint_type:
                continue
            for item in datapoint.get("values", []):
                if item.get("key") == key:
                    return item.get("value")
        return None

    @staticmethod
    def _to_float(value: Any) -> float | None:
        """Convert a gateway value to float; 'NaN' and garbage become None."""
        if value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(number):
            return None
        return number

    def _raw_state(self) -> tuple[float | None, str | None]:
        """Return (target, preset) exactly as the gateway reported them.

        preset ist None, wenn das Gateway gar kein Preset mitgeschickt hat,
        und "" (leer), wenn es meldet, dass kein Preset passt.
        """
        target = self._to_float(self._read_value("temperature_ctrl", "temperature_ctrl"))
        preset = self._read_value("temperature_ctrl", "temperature_ctrl_preset")
        if preset is not None:
            preset = str(preset).strip().lower()
        return target, preset

    def _effective_state(self) -> tuple[float | None, str | None]:
        """Return (target, preset) to show: optimistic value until the gateway answers.

        Nach einem Befehl zeigen wir sofort den neuen Wert. Sobald das Gateway
        irgendeinen geaenderten Wert meldet, gilt wieder dessen Meldung.
        """
        raw = self._raw_state()
        optimistic = self._optimistic
        if optimistic is not None and optimistic["base"] != raw:
            self._optimistic = optimistic = None
        if optimistic is not None:
            return optimistic["target"], optimistic["preset"]
        return raw

    def _learn_presets(self) -> None:
        """Remember which temperature belongs to a preset the gateway reported."""
        target, preset = self._raw_state()
        if target is not None and preset in _DEVICE_TO_HA_PRESET:
            if self._preset_temps.get(preset) != target:
                _LOGGER.debug(
                    "Thermostat %s: preset %s = %s °C", self._device_id, preset, target
                )
            self._preset_temps[preset] = target

    def _preset_for_temperature(self, temperature: float | None) -> str:
        """Return the device preset name whose learned temperature matches, or ''."""
        if temperature is None:
            return ""
        for name, preset_temperature in self._preset_temps.items():
            if abs(preset_temperature - temperature) < TEMP_TOLERANCE:
                return name
        return ""

    # ------------------------------------------------------------------
    # Zustand
    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        """Thermostat gilt als nicht erreichbar, wenn das Gateway 'NaN' meldet."""
        if not super().available:
            return False
        return self._raw_state()[0] is not None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        target, _ = self._effective_state()
        if target is None:
            return None
        return max(MIN_TEMP, min(MAX_TEMP, target))

    @property
    def current_temperature(self) -> float | None:
        """Return the measured room temperature (only if reported in °C)."""
        device = self._get_device()
        for datapoint in device.get("datapoints", []):
            if datapoint.get("type") != "quantity":
                continue
            unit = None
            quantity = None
            for item in datapoint.get("values", []):
                if item.get("key") == "quantity_unit":
                    unit = str(item.get("value") or "").strip().lower()
                elif item.get("key") == "quantity":
                    quantity = item.get("value")
            if unit not in ("°c", "c"):
                continue
            number = self._to_float(quantity)
            if number is not None:
                return number
        return None

    @property
    def preset_mode(self) -> str | None:
        """Return the active preset (None if the target matches no preset)."""
        target, preset = self._effective_state()

        # 1) Das Gateway nennt ein echtes Preset: das gilt.
        if preset in _DEVICE_TO_HA_PRESET:
            return _DEVICE_TO_HA_PRESET[preset]

        # 2) Sonst vergleichen wir die Solltemperatur mit den gelernten Werten.
        matched = self._preset_for_temperature(target)
        if matched:
            return _DEVICE_TO_HA_PRESET[matched]

        # 3) Kein Preset passt: nichts anzeigen (und "Ohne" gibt es nicht).
        return None

    # ------------------------------------------------------------------
    # Befehle
    # ------------------------------------------------------------------
    async def _async_send(self, key: str, value: str) -> None:
        """Send one value to the thermostat's temperature_ctrl datapoint."""
        url = (
            f"https://{self.coordinator.ip}/api/junghome/functions/"
            f"{self._device_id}/datapoints/{self._ctrl_id}"
        )
        body = {"data": [{"key": key, "value": value}]}
        response = await JunghomeGateway.http_patch_request(
            url, self.coordinator.token, body
        )
        if response is None:
            _LOGGER.error(
                "Failed to send %s=%s to thermostat %s", key, value, self._device_id
            )
            raise HomeAssistantError(
                f"Thermostat '{self._attr_name}': Das Gateway hat den Befehl "
                f"{key}={value} nicht angenommen (Details im Protokoll)."
            )
        _LOGGER.debug(
            "Thermostat %s: %s=%s accepted: %s", self._device_id, key, value, response
        )

    # SET TARGET TEMPERATURE
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set a new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        # auf 0,5 °C runden und auf den erlaubten Bereich begrenzen
        temperature = round(float(temperature) * 2) / 2
        temperature = max(MIN_TEMP, min(MAX_TEMP, temperature))
        value = f"{temperature:g}"  # 21.0 -> "21", 21.5 -> "21.5"

        base = self._raw_state()
        await self._async_send("temperature_ctrl", value)

        # Sofort anzeigen. Passt die Temperatur zu einem gelernten Preset,
        # wird dieses gleich mit angezeigt.
        self._optimistic = {
            "base": base,
            "target": temperature,
            "preset": self._preset_for_temperature(temperature),
        }
        self.async_write_ha_state()

    # SET PRESET
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set Frost / Eco / Komfort."""
        device_preset = _HA_TO_DEVICE_PRESET.get(preset_mode)
        if device_preset is None:
            # Unbekanntes Preset: das Gateway kennt nur diese drei.
            _LOGGER.debug(
                "Thermostat %s: preset %r cannot be set, nothing sent",
                self._device_id,
                preset_mode,
            )
            return

        base = self._raw_state()
        await self._async_send("temperature_ctrl_preset", device_preset)

        # Ist die Temperatur des Presets schon bekannt, zeigen wir sie sofort an;
        # sonst bleibt die alte Temperatur stehen, bis das Gateway die neue meldet.
        learned = self._preset_temps.get(device_preset)
        current_target, _ = self._effective_state()
        self._optimistic = {
            "base": base,
            "target": learned if learned is not None else current_target,
            "preset": device_preset,
        }
        self.async_write_ha_state()

    # SET HVAC MODE
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Accept 'heat' (the only mode); the regulator has no off switch."""
        _LOGGER.debug(
            "Thermostat %s is heat-only; ignoring set_hvac_mode(%s)",
            self._device_id,
            hvac_mode,
        )
