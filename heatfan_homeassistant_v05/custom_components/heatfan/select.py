"""Modus-keuze (1-6) voor Heatfan."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeatfanCoordinator
from .api import HeatfanError
from .const import DOMAIN, MODES
from .entity import HeatfanEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HeatfanCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(HeatfanModeSelect(coordinator, device_id) for device_id in coordinator.data)


class HeatfanModeSelect(HeatfanEntity, SelectEntity):
    """Kies de modus van de controller."""

    _attr_translation_key = "mode"
    _attr_options = MODES
    _attr_icon = "mdi:fan-speed-3"

    def __init__(self, coordinator: HeatfanCoordinator, device_id: str) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_mode"

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        return {
            "heatfan_controller": self._device_id,
            "heatfan_room": self._device.get("room"),
        }

    @property
    def current_option(self) -> str | None:
        mode = (self._data.get("user") or {}).get("mode")
        return str(mode) if str(mode) in MODES else None

    async def async_select_option(self, option: str) -> None:
        room = self._device.get("room")
        if room is None:
            raise HomeAssistantError("Controller niet gevonden")
        current = (self._data.get("user") or {}).get("mode")
        # in hetzelfde type schrijven als de bestaande waarde (tekst of getal)
        value = option if isinstance(current, str) else int(option)
        try:
            await self.coordinator.api.async_set_mode(room, self._device_id, value)
        except HeatfanError as err:
            raise HomeAssistantError(f"Modus instellen mislukt: {err}") from err

        # direct tonen, daarna ververst de coordinator vanuit de database
        self._data.setdefault("user", {})["mode"] = value
        self.coordinator.async_set_updated_data(self.coordinator.data)
        await self.coordinator.async_request_refresh()
