"""Tests for remembering/restoring the normal light state."""

from custom_components.room_nightlight.memory import (
    capture,
    level_calls,
    merge,
    percent_to_brightness,
    restore_calls,
)

DESK = "light.desk_light_finn"
WLED = "light.wled_frontlight"
EFFECTS = {WLED: ["Solid", "Candle", "Rainbow"], DESK: ["colorloop", "off"]}


def test_capture_color_temp_rgb_effect_off_and_unavailable():
    assert capture("on", {"brightness": 112, "color_mode": "color_temp", "color_temp_kelvin": 4000}) == {
        "on": True,
        "brightness": 112,
        "color_temp_kelvin": 4000,
    }
    assert capture("on", {"brightness": 200, "color_mode": "rgb", "rgb_color": (255, 120, 0), "effect": "Candle"}) == {
        "on": True,
        "brightness": 200,
        "rgb_color": [255, 120, 0],
        "effect": "Candle",
    }
    assert "effect" not in capture("on", {"brightness": 5, "color_mode": "rgb", "rgb_color": (1, 2, 3), "effect": "Solid"})
    assert capture("off", {}) == {"on": False}
    assert capture("unavailable", {}) is None


def test_merge_keeps_old_value_of_unavailable_light():
    old = {WLED: {"on": True, "brightness": 80, "rgb_color": [1, 2, 3]}}
    assert merge(old, {WLED: None, DESK: {"on": False}}) == {**old, DESK: {"on": False}}


def test_restore_calls():
    saved = {
        DESK: {"on": True, "brightness": 112, "color_temp_kelvin": 4000},
        WLED: {"on": False},
    }
    assert restore_calls(saved, [DESK, WLED], EFFECTS, 0) == [
        ("turn_on", DESK, {"brightness": 112, "color_temp_kelvin": 4000}),
        ("turn_off", WLED, {}),
    ]


def test_restore_without_saved_state_and_wled_solid():
    calls = restore_calls({}, [WLED], EFFECTS, 1)
    assert calls == [
        ("turn_on", WLED, {"brightness": 255, "color_temp_kelvin": 2700, "effect": "Solid", "transition": 1})
    ]


def test_restore_keeps_saved_effect():
    saved = {WLED: {"on": True, "brightness": 90, "rgb_color": [255, 0, 0], "effect": "Candle"}}
    assert restore_calls(saved, [WLED], EFFECTS, 0)[0][2]["effect"] == "Candle"


def test_level_calls_for_night_light():
    calls = level_calls([DESK, WLED], 26, 2000, EFFECTS, 0)
    assert calls == [
        ("turn_on", DESK, {"brightness": 26, "color_temp_kelvin": 2000}),
        ("turn_on", WLED, {"brightness": 26, "color_temp_kelvin": 2000, "effect": "Solid"}),
    ]


def test_percent_to_brightness():
    assert percent_to_brightness(0.8) == 2  # hallway: smallest visible level
    assert percent_to_brightness(10) == 26
    assert percent_to_brightness(0) == 1
    assert percent_to_brightness(100) == 255
