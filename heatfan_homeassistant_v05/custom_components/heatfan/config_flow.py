"""Config flow voor Heatfan."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import HeatfanApi, HeatfanAuthError, HeatfanError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HeatfanConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Inloggen met je Heatfan-account."""

    VERSION = 1

    async def _validate(self, email: str, password: str) -> tuple[str | None, str | None]:
        """Probeer in te loggen. Geeft (uid, fout) terug."""
        api = HeatfanApi(async_get_clientsession(self.hass), email, password)
        try:
            await api.async_login()
            devices = await api.async_get_devices()
        except HeatfanAuthError:
            return None, "invalid_auth"
        except HeatfanError:
            return None, "cannot_connect"
        except Exception:  # noqa: BLE001
            _LOGGER.exception("Onverwachte fout bij het controleren van het Heatfan-account")
            return None, "unknown"
        if not devices:
            return None, "no_devices"
        return api.uid, None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        errors: dict[str, str] = {}
        if user_input is not None:
            uid, error = await self._validate(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            if error:
                errors["base"] = error
            else:
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=user_input[CONF_EMAIL], data=user_input)

        schema = vol.Schema(
            {vol.Required(CONF_EMAIL): str, vol.Required(CONF_PASSWORD): str}
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors: dict[str, str] = {}
        if user_input is not None and entry is not None:
            _, error = await self._validate(entry.data[CONF_EMAIL], user_input[CONF_PASSWORD])
            if error:
                errors["base"] = error
            else:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            errors=errors,
        )
