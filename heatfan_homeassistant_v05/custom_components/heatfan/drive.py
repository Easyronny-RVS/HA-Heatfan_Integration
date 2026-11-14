"""Logica voor de curve-instellingen per modus (geen Home Assistant nodig)."""
from __future__ import annotations

from typing import Any

from .const import SPEED_RANGE, TEMP_RANGE

FIELDS = ("start-temp", "max-temp", "start-speed", "max-speed")


def _to_int(raw: Any) -> int | None:
    try:
        return int(round(float(raw)))
    except (TypeError, ValueError):
        return None


def build_payload_multi(current: dict[str, Any], changes: dict[str, Any]) -> dict[str, Any]:
    """Geef de vier waarden voor één modus terug, met `changes` toegepast.

    Controleert het bereik van elke waarde en dat start niet boven max ligt.
    Elke waarde wordt in hetzelfde type geschreven als de bestaande waarde (getal
    of tekst), zodat de controller het formaat herkent. Gooit ValueError met een
    duidelijke melding.
    """
    if not changes:
        raise ValueError("Geen waarden opgegeven")
    values = {f: _to_int(current.get(f)) for f in FIELDS}
    for field, new_value in changes.items():
        if field not in FIELDS:
            raise ValueError(f"Onbekend veld: {field}")
        value = _to_int(new_value)
        if value is None:
            raise ValueError("Ongeldige waarde")
        low, high = TEMP_RANGE if field.endswith("temp") else SPEED_RANGE
        if not low <= value <= high:
            raise ValueError(f"Waarde moet tussen {low} en {high} liggen")
        values[field] = value

    if any(v is None for v in values.values()):
        raise ValueError("De huidige instellingen van deze modus zijn onvolledig")
    if values["start-temp"] > values["max-temp"]:
        raise ValueError("De starttemperatuur mag niet hoger zijn dan de maximumtemperatuur")
    if values["start-speed"] > values["max-speed"]:
        raise ValueError("De startsnelheid mag niet hoger zijn dan de maximumsnelheid")

    return {
        f: (str(values[f]) if isinstance(current.get(f), str) else values[f]) for f in FIELDS
    }


def build_payload(current: dict[str, Any], field: str, new_value: float) -> dict[str, Any]:
    """Zoals build_payload_multi, maar voor één veld."""
    return build_payload_multi(current, {field: new_value})
