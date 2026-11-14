"""Eenvoudige client voor de Heatfan-cloud (Firebase Realtime Database)."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import API_KEY, DB_URL, ROOT

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = ClientTimeout(total=20)


class HeatfanError(Exception):
    """Algemene fout bij het praten met de Heatfan-cloud."""


class HeatfanAuthError(HeatfanError):
    """Inloggen mislukt of geen toegang."""


class HeatfanApi:
    """Praat met Firebase Auth en de Realtime Database van Heatfan."""

    def __init__(self, session: ClientSession, email: str, password: str) -> None:
        self._session = session
        self._email = email
        self._password = password
        self.uid: str | None = None
        self._id_token: str | None = None
        self._expires_at: float = 0.0

    async def async_login(self) -> None:
        """Log in met e-mail en wachtwoord."""
        url = (
            "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
            f"?key={API_KEY}"
        )
        payload = {
            "email": self._email,
            "password": self._password,
            "returnSecureToken": True,
        }
        try:
            async with self._session.post(url, json=payload, timeout=_TIMEOUT) as resp:
                data = await resp.json(content_type=None)
                if resp.status != 200:
                    message = str((data or {}).get("error", {}).get("message", ""))
                    if resp.status == 400 and not message.startswith("TOO_MANY"):
                        raise HeatfanAuthError(message or "inloggen mislukt")
                    raise HeatfanError(f"inloggen gaf HTTP {resp.status}: {message}")
        except (ClientError, asyncio.TimeoutError) as err:
            raise HeatfanError(f"geen verbinding bij inloggen: {err}") from err

        self._id_token = data["idToken"]
        self.uid = data["localId"]
        self._expires_at = time.time() + int(data.get("expiresIn", 3600)) - 120

    async def _ensure_token(self) -> None:
        if not self._id_token or time.time() >= self._expires_at:
            await self.async_login()

    async def _request(
        self, method: str, path: str, *, body: Any = None, retry: bool = True
    ) -> Any:
        await self._ensure_token()
        url = f"{DB_URL}/{path}.json"
        try:
            async with self._session.request(
                method,
                url,
                params={"auth": self._id_token},
                json=body,
                timeout=_TIMEOUT,
            ) as resp:
                if resp.status == 401 and retry:
                    # token verlopen of ingetrokken: opnieuw inloggen en nog 1x proberen
                    self._id_token = None
                    return await self._request(method, path, body=body, retry=False)
                if resp.status in (401, 403):
                    raise HeatfanAuthError("geen toegang tot de gegevens")
                if resp.status != 200:
                    raise HeatfanError(f"HTTP {resp.status} bij {method} {path}")
                return await resp.json(content_type=None)
        except (ClientError, asyncio.TimeoutError) as err:
            raise HeatfanError(f"verbindingsfout: {err}") from err

    async def async_get_devices(self) -> dict[str, dict[str, Any]]:
        """Haal alle controllers op: {controller_id: {"room": kamer, "data": {...}}}."""
        await self._ensure_token()
        tree = await self._request("GET", f"{ROOT}/{self.uid}/room")
        devices: dict[str, dict[str, Any]] = {}
        for room, devs in (tree or {}).items():
            if not isinstance(devs, dict):
                continue
            for dev_id, node in devs.items():
                if isinstance(node, dict):
                    devices[dev_id] = {"room": room, "data": node}
        return devices

    async def async_set_mode(self, room: str, device_id: str, mode: Any) -> None:
        """Zet de modus (1-6) van een controller (waarde wordt ongewijzigd geschreven)."""
        await self._ensure_token()
        path = f"{ROOT}/{self.uid}/room/{room}/{device_id}/user/mode"
        await self._request("PUT", path, body=mode)

    async def async_set_drive_params(
        self, room: str, device_id: str, mode_number: int, values: dict[str, Any]
    ) -> None:
        """Schrijf de vier curve-waarden van één modus in één keer (zoals 'Opslaan' in de app)."""
        await self._ensure_token()
        path = (
            f"{ROOT}/{self.uid}/room/{room}/{device_id}"
            f"/user/drive-params/mode-{mode_number}"
        )
        await self._request("PATCH", path, body=values)
