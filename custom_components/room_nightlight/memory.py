"""Remembering and restoring the "normal" state of lights.

Pure functions working on plain dicts (state + attributes), so they can be
tested without Home Assistant. One saved value per light:

* ``{"on": False}`` – the light was off
* ``{"on": True, "brightness": 112, "color_temp_kelvin": 4000}``
* ``{"on": True, "brightness": 200, "rgb_color": [255, 120, 0], "effect": "Candle"}``
"""

from __future__ import annotations

from typing import Any

NEUTRAL_EFFECTS = {"off", "None", "none", "Solid"}
DEFAULT_ON = {"brightness": 255, "color_temp_kelvin": 2700}


def capture(state: str, attributes: dict[str, Any]) -> dict[str, Any] | None:
    """Saved value for one light, or None if it is unavailable."""
    if state == "off":
        return {"on": False}
    if state != "on":
        return None
    value: dict[str, Any] = {"on": True, "brightness": int(attributes.get("brightness") or 255)}
    mode = attributes.get("color_mode")
    if mode == "color_temp" and attributes.get("color_temp_kelvin"):
        value["color_temp_kelvin"] = int(attributes["color_temp_kelvin"])
    elif attributes.get("rgb_color"):
        value["rgb_color"] = [int(c) for c in attributes["rgb_color"]]
    effect = attributes.get("effect")
    if effect and effect not in NEUTRAL_EFFECTS:
        value["effect"] = effect
    return value


def merge(old: dict[str, Any], captured: dict[str, dict[str, Any] | None]) -> dict[str, Any]:
    """New saved state; unavailable lights keep their old value."""
    result = dict(old)
    for entity_id, value in captured.items():
        if value is not None:
            result[entity_id] = value
    return result


def restore_calls(
    saved: dict[str, Any],
    lights: list[str],
    effect_lists: dict[str, list[str]],
    transition: float,
) -> list[tuple[str, str, dict[str, Any]]]:
    """Service calls (service, entity_id, data) that restore the saved state.

    Without anything saved yet, every light goes to 100 % / 2700 K.
    """
    calls: list[tuple[str, str, dict[str, Any]]] = []
    for entity_id in lights:
        value = saved.get(entity_id)
        if value is not None and not value.get("on", True):
            calls.append(("turn_off", entity_id, _with_transition({}, transition)))
            continue
        data: dict[str, Any] = dict(DEFAULT_ON)
        if value is not None:
            data = {"brightness": value.get("brightness", 255)}
            if "color_temp_kelvin" in value:
                data["color_temp_kelvin"] = value["color_temp_kelvin"]
            elif "rgb_color" in value:
                data["rgb_color"] = value["rgb_color"]
        effect = (value or {}).get("effect")
        if effect:
            data["effect"] = effect
        elif "Solid" in effect_lists.get(entity_id, []):
            data["effect"] = "Solid"  # stop a running WLED effect
        calls.append(("turn_on", entity_id, _with_transition(data, transition)))
    return calls


def level_calls(
    lights: list[str],
    brightness: int,
    kelvin: int,
    effect_lists: dict[str, list[str]],
    transition: float,
) -> list[tuple[str, str, dict[str, Any]]]:
    """Service calls for a fixed level (night light, auto light)."""
    calls = []
    for entity_id in lights:
        data: dict[str, Any] = {"brightness": brightness, "color_temp_kelvin": kelvin}
        if "Solid" in effect_lists.get(entity_id, []):
            data["effect"] = "Solid"
        calls.append(("turn_on", entity_id, _with_transition(data, transition)))
    return calls


def percent_to_brightness(percent: float) -> int:
    """0.8 % → 2, 10 % → 26; never 0 (that would be off)."""
    return max(1, min(255, round(percent * 255 / 100)))


def _with_transition(data: dict[str, Any], transition: float) -> dict[str, Any]:
    if transition > 0:
        return {**data, "transition": transition}
    return data
