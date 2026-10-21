"""Home Assistant glue for one room light: listens, decides, switches."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ENTITY_ID, STATE_ON
from homeassistant.core import (
    CALLBACK_TYPE,
    Context,
    Event,
    EventStateChangedData,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.event import async_call_later, async_track_state_change_event
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AUTO_BRIGHTNESS,
    CONF_AUTO_KELVIN,
    CONF_AUTO_OFF_DELAY,
    CONF_BUTTON_COMMAND,
    CONF_BUTTON_IEEE,
    CONF_ILLUMINANCE,
    CONF_LIGHT,
    CONF_LIGHTS,
    CONF_LUX_THRESHOLD,
    CONF_NAME,
    CONF_NIGHT_BRIGHTNESS,
    CONF_NIGHT_KELVIN,
    CONF_NIGHT_OFF_DELAY,
    CONF_OCCUPANCY,
    CONF_QUIET,
    CONF_TRANSITION,
    DEFAULTS,
    DOMAIN,
    EVENT_MODE_CHANGED,
    MEMORY_DEBOUNCE_SECONDS,
    MEMORY_SETTLE_SECONDS,
    SAVE_DELAY_SECONDS,
    STORAGE_VERSION,
)
from .engine import (
    Action,
    Decision,
    Env,
    Mode,
    on_button,
    on_light_external,
    on_mode_selected,
    on_occupied,
    on_start,
    on_vacant,
)
from .memory import capture, level_calls, merge, percent_to_brightness, restore_calls

_LOGGER = logging.getLogger(__name__)


class RoomLightController:
    """Owns the mode of one room light."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        opt = {**DEFAULTS, **entry.options}
        self.name: str = entry.data[CONF_NAME]
        self.light: str = opt[CONF_LIGHT]
        self._configured_lights: list[str] = list(opt.get(CONF_LIGHTS) or [])
        self.occupancy: list[str] = list(opt.get(CONF_OCCUPANCY) or [])
        self.illuminance: str | None = opt.get(CONF_ILLUMINANCE)
        self.lux_threshold = float(opt[CONF_LUX_THRESHOLD])
        self.quiet_entity: str | None = opt.get(CONF_QUIET)
        self.button_ieee: str | None = (opt.get(CONF_BUTTON_IEEE) or "").strip().lower() or None
        self.button_command: str = opt[CONF_BUTTON_COMMAND]
        self.night_brightness = percent_to_brightness(float(opt[CONF_NIGHT_BRIGHTNESS]))
        self.night_kelvin = int(opt[CONF_NIGHT_KELVIN])
        self.auto_brightness = percent_to_brightness(float(opt[CONF_AUTO_BRIGHTNESS]))
        self.auto_kelvin = int(opt[CONF_AUTO_KELVIN])
        self.night_off_delay = float(opt[CONF_NIGHT_OFF_DELAY]) * 60
        self.auto_off_delay = float(opt[CONF_AUTO_OFF_DELAY]) * 60
        self.transition = float(opt[CONF_TRANSITION])

        self.mode = Mode.OFF
        self.mode_since = dt_util.utcnow().timestamp()
        self.last_reason = ""
        self.motion_enabled = True
        self.normal: dict[str, Any] = {}

        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._own: deque[str] = deque(maxlen=32)
        self._listeners: list[Callable[[], None]] = []
        self._unsubs: list[CALLBACK_TYPE] = []
        self._vacancy_timers: list[CALLBACK_TYPE] = []
        self._memory_timer: CALLBACK_TYPE | None = None

    # ------------------------------------------------------------------ lifecycle

    async def async_start(self) -> None:
        if (data := await self._store.async_load()) is not None:
            try:
                self.mode = Mode(data.get("mode", Mode.OFF))
                self.motion_enabled = bool(data.get("motion_enabled", True))
                self.normal = dict(data.get("normal") or {})
                self.last_reason = data.get("last_reason", "")
            except ValueError:
                _LOGGER.warning("Stored state of %s is invalid, starting fresh", self.name)

        self._unsubs.append(
            async_track_state_change_event(self.hass, self.occupancy, self._on_occupancy)
        )
        self._unsubs.append(
            async_track_state_change_event(self.hass, [self.light], self._on_main_light)
        )
        self._unsubs.append(
            async_track_state_change_event(self.hass, self.lights, self._on_member_light)
        )
        if self.button_ieee:
            self._unsubs.append(self.hass.bus.async_listen("zha_event", self._on_zha_event))

        await self._apply(on_start(self.mode, self._light_on()))
        if self.mode in (Mode.NIGHT, Mode.AUTO) and not self._occupied():
            self._schedule_vacancy()

    async def async_stop(self) -> None:
        for unsub in [*self._unsubs, *self._vacancy_timers]:
            unsub()
        self._unsubs.clear()
        self._vacancy_timers.clear()
        if self._memory_timer is not None:
            self._memory_timer()
        await self._store.async_save(self._data())

    # ------------------------------------------------------------------ public

    @callback
    def async_add_listener(self, update: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.append(update)

        @callback
        def remove() -> None:
            self._listeners.remove(update)

        return remove

    @property
    def lights(self) -> list[str]:
        """Lights that are switched and remembered (default: members of the group)."""
        if self._configured_lights:
            return self._configured_lights
        state = self.hass.states.get(self.light)
        members = state.attributes.get(ATTR_ENTITY_ID) if state else None
        if isinstance(members, (list, tuple)) and members:
            return list(members)
        return [self.light]

    async def async_select_mode(self, mode: Mode) -> None:
        await self._apply(on_mode_selected(self.mode, mode))

    @callback
    def async_set_motion_enabled(self, enabled: bool) -> None:
        self.motion_enabled = enabled
        self._save()
        self._notify()

    # ------------------------------------------------------------------ listeners

    async def _on_occupancy(self, event: Event[EventStateChangedData]) -> None:
        if self._occupied():
            self._cancel_vacancy()
            await self._apply(on_occupied(self.mode, self._env()))
        else:
            self._schedule_vacancy()

    async def _on_zha_event(self, event: Event) -> None:
        data = event.data
        if (
            str(data.get("device_ieee", "")).lower() == self.button_ieee
            and data.get("command") == self.button_command
        ):
            await self._apply(on_button(self.mode, self._env()))

    async def _on_main_light(self, event: Event[EventStateChangedData]) -> None:
        old, new = event.data["old_state"], event.data["new_state"]
        if new is None or new.state not in ("on", "off"):
            return
        if old is not None and old.state == new.state:
            # Attribute change only (brightness, color): may be a new normal state.
            self._on_member_light(event)
            return
        if old is None or old.state not in ("on", "off"):
            return  # coming back from unavailable is not a switch
        if self._is_own(event):
            return
        await self._apply(on_light_external(self.mode, new.state == STATE_ON))

    @callback
    def _on_member_light(self, event: Event[EventStateChangedData]) -> None:
        if self._is_own(event) or self.mode is not Mode.MANUAL:
            return
        if dt_util.utcnow().timestamp() - self.mode_since < MEMORY_SETTLE_SECONDS:
            return
        if self._memory_timer is not None:
            self._memory_timer()
        self._memory_timer = async_call_later(
            self.hass, MEMORY_DEBOUNCE_SECONDS, self._remember_normal
        )

    @callback
    def _remember_normal(self, _now: datetime) -> None:
        self._memory_timer = None
        if self.mode is not Mode.MANUAL or not self._light_on():
            return
        captured = {}
        for entity_id in self.lights:
            state = self.hass.states.get(entity_id)
            captured[entity_id] = (
                capture(state.state, dict(state.attributes)) if state is not None else None
            )
        self.normal = merge(self.normal, captured)
        self._save()
        self._notify()

    # ------------------------------------------------------------------ vacancy

    @callback
    def _schedule_vacancy(self) -> None:
        self._cancel_vacancy()
        for delay, timer in ((self.night_off_delay, Mode.NIGHT), (self.auto_off_delay, Mode.AUTO)):

            async def fire(_now: datetime, timer: Mode = timer) -> None:
                if not self._occupied():
                    await self._apply(on_vacant(self.mode, timer))

            self._vacancy_timers.append(async_call_later(self.hass, delay, fire))

    @callback
    def _cancel_vacancy(self) -> None:
        for unsub in self._vacancy_timers:
            unsub()
        self._vacancy_timers.clear()

    # ------------------------------------------------------------------ decisions

    async def _apply(self, decision: Decision) -> None:
        if decision.mode is not None and decision.mode is not self.mode:
            old = self.mode
            self.mode = decision.mode
            self.mode_since = dt_util.utcnow().timestamp()
            self.last_reason = decision.reason
            self.hass.bus.async_fire(
                EVENT_MODE_CHANGED,
                {
                    "config_entry_id": self.entry.entry_id,
                    "name": self.name,
                    "from": old.value,
                    "to": self.mode.value,
                    "reason": decision.reason,
                },
            )
            if self.mode in (Mode.NIGHT, Mode.AUTO) and not self._occupied():
                self._schedule_vacancy()
            self._save()
            self._notify()
        if decision.action is not None:
            await self._run(decision.action)

    async def _run(self, action: Action) -> None:
        effects = {
            eid: list((s.attributes.get("effect_list") or []) if (s := self.hass.states.get(eid)) else [])
            for eid in self.lights
        }
        if action is Action.NIGHT_ON:
            calls = level_calls(self.lights, self.night_brightness, self.night_kelvin, effects, self.transition)
        elif action is Action.AUTO_ON:
            calls = level_calls(self.lights, self.auto_brightness, self.auto_kelvin, effects, self.transition)
        elif action is Action.RESTORE:
            calls = restore_calls(self.normal, self.lights, effects, self.transition)
        else:
            calls = [("turn_off", self.light, {"transition": self.transition} if self.transition else {})]

        context = Context()
        self._own.append(context.id)
        for service, entity_id, data in calls:
            try:
                await self.hass.services.async_call(
                    "light",
                    service,
                    {ATTR_ENTITY_ID: entity_id, **data},
                    blocking=False,
                    context=context,
                )
            except Exception:  # noqa: BLE001 - one broken lamp must not stop the others
                _LOGGER.exception("%s: light.%s failed for %s", self.name, service, entity_id)

    # ------------------------------------------------------------------ helpers

    def _is_own(self, event: Event) -> bool:
        ctx = event.context
        return ctx.id in self._own or (ctx.parent_id is not None and ctx.parent_id in self._own)

    def _occupied(self) -> bool:
        return any(self.hass.states.is_state(e, STATE_ON) for e in self.occupancy)

    def _light_on(self) -> bool:
        return self.hass.states.is_state(self.light, STATE_ON)

    def _env(self) -> Env:
        lux = None
        if self.illuminance and (state := self.hass.states.get(self.illuminance)):
            try:
                lux = float(state.state)
            except ValueError:
                lux = None
        return Env(
            occupied=self._occupied(),
            light_on=self._light_on(),
            is_night=self.hass.states.is_state("sun.sun", "below_horizon"),
            lux=lux,
            lux_threshold=self.lux_threshold if self.illuminance else None,
            quiet=bool(self.quiet_entity) and self.hass.states.is_state(self.quiet_entity, STATE_ON),
            motion_enabled=self.motion_enabled,
        )

    def _data(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "motion_enabled": self.motion_enabled,
            "normal": self.normal,
            "last_reason": self.last_reason,
        }

    @callback
    def _save(self) -> None:
        self._store.async_delay_save(self._data, SAVE_DELAY_SECONDS)

    @callback
    def _notify(self) -> None:
        for update in list(self._listeners):
            update()
