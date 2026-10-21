"""Switch: lets motion switch the light on (pause for guests, parties ...)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import RoomLightEntity

if TYPE_CHECKING:
    from . import RoomNightLightConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RoomNightLightConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([MotionSwitch(entry.runtime_data, "motion")])


class MotionSwitch(RoomLightEntity, SwitchEntity):
    _attr_entity_category = EntityCategory.CONFIG

    @property
    def is_on(self) -> bool:
        return self.controller.motion_enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        self.controller.async_set_motion_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        self.controller.async_set_motion_enabled(False)
