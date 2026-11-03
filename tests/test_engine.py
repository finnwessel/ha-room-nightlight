"""Tests for the room light state machine (no Home Assistant needed)."""

from custom_components.room_nightlight.engine import (
    NOTHING,
    Action,
    Decision,
    Env,
    Mode,
    on_button,
    on_light_adjusted,
    on_light_external,
    on_mode_selected,
    on_occupied,
    on_start,
    on_vacant,
)


def env(**kw):
    base = {"occupied": True, "light_on": False, "is_night": True}
    return Env(**{**base, **kw})


# --- motion ------------------------------------------------------------------


def test_motion_at_night_switches_night_light_on():
    assert on_occupied(Mode.OFF, env()) == Decision(Mode.NIGHT, Action.NIGHT_ON, "motion_at_night")


def test_motion_during_day_only_when_dark_and_lux_configured():
    day = env(is_night=False)
    assert on_occupied(Mode.OFF, day) is NOTHING  # kitchen/office: no lux sensor
    assert on_occupied(Mode.OFF, env(is_night=False, lux=10, lux_threshold=25)).mode is Mode.AUTO
    assert on_occupied(Mode.OFF, env(is_night=False, lux=500, lux_threshold=25)) is NOTHING


def test_motion_ignored_when_light_on_quiet_disabled_or_not_off():
    assert on_occupied(Mode.OFF, env(light_on=True)) is NOTHING
    assert on_occupied(Mode.OFF, env(quiet=True)) is NOTHING
    assert on_occupied(Mode.OFF, env(motion_enabled=False)) is NOTHING
    assert on_occupied(Mode.MANUAL, env()) is NOTHING


def test_vacancy_turns_off_only_matching_automatic_mode():
    assert on_vacant(Mode.NIGHT, Mode.NIGHT) == Decision(Mode.OFF, Action.TURN_OFF, "no_motion")
    assert on_vacant(Mode.AUTO, Mode.AUTO).action is Action.TURN_OFF
    assert on_vacant(Mode.AUTO, Mode.NIGHT) is NOTHING  # 1-min timer must not end auto (2 min)
    assert on_vacant(Mode.MANUAL, Mode.NIGHT) is NOTHING  # manual is never switched off


# --- button ------------------------------------------------------------------


def test_button_cycle_like_kitchen_and_office():
    assert on_button(Mode.NIGHT, env()) == Decision(Mode.MANUAL, Action.RESTORE, "button")
    assert on_button(Mode.MANUAL, env()) == Decision(Mode.NIGHT, Action.NIGHT_ON, "button")
    assert on_button(Mode.MANUAL, env(occupied=False)).mode is Mode.OFF
    assert on_button(Mode.MANUAL, env(is_night=False)).action is Action.TURN_OFF
    assert on_button(Mode.OFF, env()) == Decision(Mode.MANUAL, Action.RESTORE, "button")
    assert on_button(Mode.AUTO, env()).mode is Mode.MANUAL


# --- outside changes ---------------------------------------------------------


def test_outside_switching_syncs_mode():
    assert on_light_external(Mode.NIGHT, False) == Decision(Mode.OFF, None, "switched_off_outside")
    assert on_light_external(Mode.MANUAL, False).mode is Mode.OFF
    assert on_light_external(Mode.OFF, False) is NOTHING
    assert on_light_external(Mode.OFF, True) == Decision(Mode.MANUAL, None, "switched_on_outside")
    assert on_light_external(Mode.NIGHT, True) is NOTHING


def test_selecting_a_mode_runs_its_action():
    assert on_mode_selected(Mode.OFF, Mode.NIGHT).action is Action.NIGHT_ON
    assert on_mode_selected(Mode.NIGHT, Mode.MANUAL).action is Action.RESTORE
    assert on_mode_selected(Mode.MANUAL, Mode.OFF).action is Action.TURN_OFF
    assert on_mode_selected(Mode.AUTO, Mode.AUTO) is NOTHING


def test_restart_brings_mode_in_line_with_light():
    assert on_start(Mode.NIGHT, False).mode is Mode.OFF
    assert on_start(Mode.OFF, True).mode is Mode.MANUAL
    assert on_start(Mode.MANUAL, True) is NOTHING
    assert on_start(Mode.OFF, False) is NOTHING


# --- full scenario (kitchen at night) -------------------------------------------


def test_kitchen_night_scenario():
    mode = Mode.OFF
    d = on_occupied(mode, env())
    mode = d.mode
    # our own light change arrives while mode is already night → no sync
    assert on_light_external(mode, True) is NOTHING
    d = on_button(mode, env(light_on=True))
    mode = d.mode
    assert d.action is Action.RESTORE and mode is Mode.MANUAL
    # no-motion timers do not touch manual
    assert on_vacant(mode, Mode.NIGHT) is NOTHING
    d = on_button(mode, env(light_on=True, occupied=False))
    assert d == Decision(Mode.OFF, Action.TURN_OFF, "button")


# --- night entity (quiet hours instead of sunset) -------------------------------


def test_evening_with_night_entity_gets_auto_level():
    evening = env(is_night=False, sun_down=True)
    assert on_occupied(Mode.OFF, evening) == Decision(Mode.AUTO, Action.AUTO_ON, "motion_in_dark")
    # sun down counts as dark even when the lux sensor still reads the old value
    assert on_occupied(Mode.OFF, env(is_night=False, sun_down=True, lux=35, lux_threshold=25)).mode is Mode.AUTO
    assert on_occupied(Mode.OFF, env(is_night=True, sun_down=True)).mode is Mode.NIGHT


def test_quiet_hours_still_block_motion_at_night():
    assert on_occupied(Mode.OFF, env(is_night=True, sun_down=True, quiet=True)) is NOTHING


# --- dimmed by someone else --------------------------------------------------------


def test_dimming_automatic_light_makes_it_manual():
    assert on_light_adjusted(Mode.NIGHT) == Decision(Mode.MANUAL, None, "adjusted_outside")
    assert on_light_adjusted(Mode.AUTO).mode is Mode.MANUAL
    assert on_light_adjusted(Mode.MANUAL) is NOTHING
    assert on_light_adjusted(Mode.OFF) is NOTHING
    # once manual, the no-motion timers leave it alone
    assert on_vacant(Mode.MANUAL, Mode.AUTO) is NOTHING
