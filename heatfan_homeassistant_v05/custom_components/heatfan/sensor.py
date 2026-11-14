"""Sensoren voor Heatfan."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HeatfanCoordinator
from .const import DOMAIN
from .entity import HeatfanEntity


def _status(data: dict[str, Any], key: str) -> Any:
    return (data.get("status") or {}).get(key)


def _timestamp(data: dict[str, Any]) -> datetime | None:
    ts = _status(data, "timestamp")
    if ts is None:
        return None
    return datetime.fromtimestamp(float(ts), tz=timezone.utc)


@dataclass(frozen=True, kw_only=True)
class HeatfanSensorDescription(SensorEntityDescription):
    """Beschrijving van een Heatfan-sensor."""

    value_fn: Callable[[dict[str, Any]], Any]


SENSORS: tuple[HeatfanSensorDescription, ...] = (
    HeatfanSensorDescription(
        key="temp_ext",
        translation_key="radiator_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: _status(d, "temp_ext"),
    ),
    HeatfanSensorDescription(
        key="speed",
        translation_key="fan_speed",
        icon="mdi:fan",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: _status(d, "speed"),
    ),
    HeatfanSensorDescription(
        key="temp_slope",
        translation_key="temperature_trend",
        icon="mdi:trending-up",
        value_fn=lambda d: _status(d, "temp_slope"),
    ),
    HeatfanSensorDescription(
        key="temp_board",
        translation_key="board_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda d: _status(d, "temp_board"),
    ),
    HeatfanSensorDescription(
        key="temp_mcu",
        translation_key="mcu_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=1,
        value_fn=lambda d: _status(d, "temp_mcu"),
    ),
    HeatfanSensorDescription(
        key="rssi",
        translation_key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: _status(d, "rssi"),
    ),
    HeatfanSensorDescription(
        key="last_update",
        translation_key="last_update",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_timestamp,
    ),
    HeatfanSensorDescription(
        key="firmware",
        translation_key="firmware_version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: None if d.get("firmware-version") is None else str(d["firmware-version"]),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: HeatfanCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HeatfanSensor(coordinator, device_id, description)
        for device_id in coordinator.data
        for description in SENSORS
    )


class HeatfanSensor(HeatfanEntity, SensorEntity):
    """Een meetwaarde van een Heatfan-controller."""

    entity_description: HeatfanSensorDescription

    def __init__(
        self,
        coordinator: HeatfanCoordinator,
        device_id: str,
        description: HeatfanSensorDescription,
    ) -> None:
        super().__init__(coordinator, device_id)
        self.entity_description = description
        self._attr_unique_id = f"{device_id}_{description.key}"

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self._data)
