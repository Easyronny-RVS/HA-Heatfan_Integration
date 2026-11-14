"""Curve-instellingen per modus (temperatuurbereik en snelheidsbereik)."""
from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeatfanCoordinator
from .const import DOMAIN, MODES, SPEED_RANGE, TEMP_RANGE
from .entity import HeatfanEntity

# veld in de database -> (naam NL, naam EN)
# De apparaatpagina sorteert entiteiten alfabetisch op naam. De namen zijn zo gekozen dat
# de volgorde per modus is: beginsnelheid, begintemperatuur, maximumsnelheid, maximumtemperatuur.
FIELDS = {
    "start-speed": ("beginsnelheid", "initial speed"),
    "start-temp": ("begintemperatuur", "initial temperature"),
    "max-speed": ("maximumsnelheid", "maximum speed"),
    "max-temp": ("maximumtemperatuur", "maximum temperature"),
}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HeatfanCoordinator = hass.data[DOMAIN][entry.entry_id]
    dutch = str(hass.config.language).startswith("nl")
    async_add_entities(
        HeatfanDriveNumber(coordinator, device_id, int(mode), field, dutch)
        for device_id in coordinator.data
        for mode in MODES
        for field in FIELDS
    )


class HeatfanDriveNumber(HeatfanEntity, NumberEntity):
    """Eén instelling (bijvoorbeeld modus 3, maximumtemperatuur)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_mode = NumberMode.SLIDER
    _attr_native_step = 1

    def __init__(
        self,
        coordinator: HeatfanCoordinator,
        device_id: str,
        mode_number: int,
        field: str,
        dutch: bool,
    ) -> None:
        super().__init__(coordinator, device_id)
        self._mode_number = mode_number
        self._field = field
        nl, en = FIELDS[field]
        self._attr_name = f"Modus {mode_number} {nl}" if dutch else f"Mode {mode_number} {en}"
        self._attr_unique_id = f"{device_id}_mode{mode_number}_{field}"
        if field.endswith("temp"):
            self._attr_native_min_value, self._attr_native_max_value = TEMP_RANGE
            self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
            self._attr_device_class = NumberDeviceClass.TEMPERATURE
        else:
            self._attr_native_min_value, self._attr_native_max_value = SPEED_RANGE
            self._attr_icon = "mdi:fan"

    @property
    def _params(self) -> dict[str, Any]:
        user = self._data.get("user") or {}
        return (user.get("drive-params") or {}).get(f"mode-{self._mode_number}") or {}

    @property
    def native_value(self) -> float | None:
        try:
            return float(self._params.get(self._field))
        except (TypeError, ValueError):
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # de Heatfan-kaart gebruikt deze attributen om de juiste entiteiten te vinden
        return {
            "heatfan_controller": self._device_id,
            "heatfan_room": self._device.get("room"),
            "heatfan_mode": self._mode_number,
            "heatfan_field": self._field,
        }

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_set_curve(
            self._device_id, self._mode_number, {self._field: value}
        )
