"""Room Night Light: night light, auto light and remembered normal state per room light.

Each config entry is one light (or light group) with its motion sensors.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .controller import RoomLightController

PLATFORMS: list[Platform] = [Platform.SELECT, Platform.SWITCH]

type RoomNightLightConfigEntry = ConfigEntry[RoomLightController]


async def async_setup_entry(hass: HomeAssistant, entry: RoomNightLightConfigEntry) -> bool:
    controller = RoomLightController(hass, entry)
    await controller.async_start()
    entry.runtime_data = controller
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RoomNightLightConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded


async def _async_reload(hass: HomeAssistant, entry: RoomNightLightConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
