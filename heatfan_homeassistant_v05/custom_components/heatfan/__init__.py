"""Heatfan-integratie voor Home Assistant (onofficieel, via de Heatfan-cloud)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import HeatfanApi, HeatfanAuthError, HeatfanError
from .const import (
    CARD_FILE,
    CARD_VERSION,
    DOMAIN,
    SCAN_INTERVAL,
    SERVICE_SET_CURVE,
    URL_BASE,
)
from .drive import build_payload_multi

try:  # nieuwere Home Assistant-versies hebben een aparte validatiefout
    from homeassistant.exceptions import ServiceValidationError
except ImportError:  # pragma: no cover
    ServiceValidationError = HomeAssistantError

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.SELECT, Platform.NUMBER]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

# service-veldnaam -> veldnaam in de database
SERVICE_FIELDS = {
    "start_temp": "start-temp",
    "max_temp": "max-temp",
    "start_speed": "start-speed",
    "max_speed": "max-speed",
}

SET_CURVE_SCHEMA = vol.Schema(
    {
        vol.Optional("controller"): cv.string,
        vol.Required("mode"): vol.All(vol.Coerce(int), vol.Range(min=1, max=6)),
        vol.Optional("start_temp"): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        vol.Optional("max_temp"): vol.All(vol.Coerce(int), vol.Range(min=1, max=100)),
        vol.Optional("start_speed"): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
        vol.Optional("max_speed"): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
    }
)


class HeatfanCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Haalt periodiek de gegevens van alle controllers op."""

    def __init__(self, hass: HomeAssistant, api: HeatfanApi) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.api = api

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            return await self.api.async_get_devices()
        except HeatfanAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except HeatfanError as err:
            raise UpdateFailed(str(err)) from err

    async def async_set_curve(
        self, device_id: str, mode_number: int, changes: dict[str, Any]
    ) -> None:
        """Pas één of meer curve-waarden van een modus aan (alle vier in één keer opgeslagen)."""
        device = (self.data or {}).get(device_id)
        if device is None:
            raise HomeAssistantError("Controller niet gevonden")
        user = (device.get("data") or {}).get("user") or {}
        current = (user.get("drive-params") or {}).get(f"mode-{mode_number}") or {}
        try:
            payload = build_payload_multi(current, changes)
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        try:
            await self.api.async_set_drive_params(device["room"], device_id, mode_number, payload)
        except HeatfanError as err:
            raise HomeAssistantError(f"Instelling opslaan mislukt: {err}") from err

        # direct tonen; daarna ververst de coordinator vanuit de database
        params = device["data"].setdefault("user", {}).setdefault("drive-params", {})
        params.setdefault(f"mode-{mode_number}", {}).update(payload)
        self.async_set_updated_data(self.data)
        await self.async_request_refresh()


def _coordinators(hass: HomeAssistant) -> list[HeatfanCoordinator]:
    return [c for c in hass.data.get(DOMAIN, {}).values() if isinstance(c, HeatfanCoordinator)]


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Registreer de service en de meegeleverde kaart (één keer)."""

    async def _handle_set_curve(call: ServiceCall) -> None:
        coordinators = _coordinators(hass)
        controller = call.data.get("controller")
        matches = [
            (c, dev_id)
            for c in coordinators
            for dev_id in (c.data or {})
            if controller is None or dev_id == controller
        ]
        if not matches:
            raise ServiceValidationError("Controller niet gevonden")
        if len(matches) > 1:
            raise ServiceValidationError(
                "Meerdere controllers gevonden: geef 'controller' op (het controller-ID)"
            )
        coordinator, device_id = matches[0]
        changes = {db: call.data[key] for key, db in SERVICE_FIELDS.items() if key in call.data}
        await coordinator.async_set_curve(device_id, call.data["mode"], changes)

    hass.services.async_register(
        DOMAIN, SERVICE_SET_CURVE, _handle_set_curve, schema=SET_CURVE_SCHEMA
    )

    # De kaart met twee schuifregelaars automatisch laden op elk dashboard.
    try:
        from homeassistant.components.frontend import add_extra_js_url
        from homeassistant.components.http import StaticPathConfig

        folder = Path(__file__).parent / "frontend"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(URL_BASE, str(folder), False)]
        )
        add_extra_js_url(hass, f"{URL_BASE}/{CARD_FILE}?v={CARD_VERSION}")
    except Exception:  # noqa: BLE001
        _LOGGER.warning(
            "De Heatfan-kaart kon niet automatisch worden geladen; de rest werkt gewoon",
            exc_info=True,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Zet de integratie op vanuit een config entry."""
    api = HeatfanApi(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
    )
    coordinator = HeatfanCoordinator(hass, api)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Ruim de integratie op."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded
