"""Diagnostics for a room light."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

if TYPE_CHECKING:
    from . import RoomNightLightConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RoomNightLightConfigEntry
) -> dict[str, Any]:
    c = entry.runtime_data
    return {
        "options": dict(entry.options),
        "mode": c.mode.value,
        "last_reason": c.last_reason,
        "motion_enabled": c.motion_enabled,
        "lights": c.lights,
        "normal": c.normal,
    }
