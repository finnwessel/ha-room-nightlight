"""State machine of one room light.

Pure Python, no Home Assistant imports. The HA glue in ``controller.py`` feeds
it what happened (occupancy, button press, light switched from outside, timer)
and executes the returned decision.

Modes::

    off ──occupied, night──────────────▶ night ──vacant night_off_delay──▶ off
    off ──occupied, day, dark (lux)────▶ auto  ──vacant auto_off_delay───▶ off
    off ──button / switched on outside─▶ manual (restores the saved normal state)
    night/auto ──button────────────────▶ manual
    manual ──button, occupied at night─▶ night
    manual ──button────────────────────▶ off
    any ──switched off outside─────────▶ off

The mode is always changed *before* the light action, so the light's own
state change caused by the action never looks like an outside change.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Mode(StrEnum):
    OFF = "off"
    NIGHT = "night"
    AUTO = "auto"
    MANUAL = "manual"


class Action(StrEnum):
    NIGHT_ON = "night_on"
    AUTO_ON = "auto_on"
    RESTORE = "restore"
    TURN_OFF = "turn_off"


@dataclass(frozen=True)
class Env:
    """What the room looks like right now."""

    occupied: bool
    light_on: bool
    is_night: bool
    lux: float | None = None
    lux_threshold: float | None = None
    quiet: bool = False  # e.g. everyone asleep: motion does not switch on
    motion_enabled: bool = True

    @property
    def dark(self) -> bool:
        return (
            self.lux is not None
            and self.lux_threshold is not None
            and self.lux < self.lux_threshold
        )


@dataclass(frozen=True)
class Decision:
    """New mode (None = unchanged) and light action (None = nothing)."""

    mode: Mode | None = None
    action: Action | None = None
    reason: str = ""


NOTHING = Decision()


def on_occupied(mode: Mode, env: Env) -> Decision:
    """Someone entered the room."""
    if mode is not Mode.OFF or env.light_on or env.quiet or not env.motion_enabled:
        return NOTHING
    if env.is_night:
        return Decision(Mode.NIGHT, Action.NIGHT_ON, "motion_at_night")
    if env.dark:
        return Decision(Mode.AUTO, Action.AUTO_ON, "motion_in_dark")
    return NOTHING


def on_vacant(mode: Mode, timer: Mode) -> Decision:
    """The room has been empty for the delay that belongs to ``timer``."""
    if mode is timer and mode in (Mode.NIGHT, Mode.AUTO):
        return Decision(Mode.OFF, Action.TURN_OFF, "no_motion")
    return NOTHING


def on_button(mode: Mode, env: Env) -> Decision:
    """The configured button was pressed."""
    if mode in (Mode.NIGHT, Mode.AUTO):
        return Decision(Mode.MANUAL, Action.RESTORE, "button")
    if mode is Mode.MANUAL:
        if env.occupied and env.is_night:
            return Decision(Mode.NIGHT, Action.NIGHT_ON, "button")
        return Decision(Mode.OFF, Action.TURN_OFF, "button")
    return Decision(Mode.MANUAL, Action.RESTORE, "button")


def on_light_external(mode: Mode, is_on: bool) -> Decision:
    """The light was switched by someone else (app, voice, scene, wall switch)."""
    if not is_on and mode is not Mode.OFF:
        return Decision(Mode.OFF, None, "switched_off_outside")
    if is_on and mode is Mode.OFF:
        return Decision(Mode.MANUAL, None, "switched_on_outside")
    return NOTHING


def on_mode_selected(mode: Mode, wanted: Mode) -> Decision:
    """The user picked a mode on the select entity."""
    if wanted is mode:
        return NOTHING
    action = {
        Mode.OFF: Action.TURN_OFF,
        Mode.NIGHT: Action.NIGHT_ON,
        Mode.AUTO: Action.AUTO_ON,
        Mode.MANUAL: Action.RESTORE,
    }[wanted]
    return Decision(wanted, action, "selected")


def on_start(mode: Mode, light_on: bool) -> Decision:
    """After a restart: bring the stored mode in line with the light."""
    if not light_on and mode is not Mode.OFF:
        return Decision(Mode.OFF, None, "restart")
    if light_on and mode is Mode.OFF:
        return Decision(Mode.MANUAL, None, "restart")
    return NOTHING
