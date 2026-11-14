"""Basisklasse voor Heatfan-entiteiten."""
from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HeatfanCoordinator
from .const import DOMAIN, MANUFACTURER


class HeatfanEntity(CoordinatorEntity[HeatfanCoordinator]):
    """Entiteit die bij één Heatfan-controller hoort."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: HeatfanCoordinator, device_id: str) -> None:
        super().__init__(coordinator)
        self._device_id = device_id

    @property
    def _device(self) -> dict[str, Any]:
        return (self.coordinator.data or {}).get(self._device_id, {})

    @property
    def _data(self) -> dict[str, Any]:
        return self._device.get("data", {})

    @property
    def available(self) -> bool:
        return super().available and self._device_id in (self.coordinator.data or {})

    @property
    def device_info(self) -> DeviceInfo:
        room = self._device.get("room", "")
        return DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=f"Heatfan {room}".strip(),
            manufacturer=MANUFACTURER,
            model="Heatfan Controller",
            sw_version=str(self._data.get("firmware-version", "")) or None,
            hw_version=str(self._data.get("hardware-version", "")) or None,
        )
