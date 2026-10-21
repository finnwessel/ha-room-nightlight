"""Mode select: shows and sets the mode of a room light."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .engine import Mode
from .entity import RoomLightEntity

if TYPE_CHECKING:
    from . import RoomNightLightConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RoomNightLightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([ModeSelect(entry.runtime_data, "mode")])


class ModeSelect(RoomLightEntity, SelectEntity):
    _attr_options = [m.value for m in Mode]

    @property
    def current_option(self) -> str:
        return self.controller.mode.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "reason": self.controller.last_reason or None,
            "lights": self.controller.lights,
            "normal_state": self.controller.normal,
        }

    async def async_select_option(self, option: str) -> None:
        await self.controller.async_select_mode(Mode(option))
