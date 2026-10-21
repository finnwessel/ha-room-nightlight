"""Constants for Room Night Light."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "room_nightlight"

CONF_NAME: Final = "name"
CONF_LIGHT: Final = "light"
CONF_LIGHTS: Final = "lights"
CONF_OCCUPANCY: Final = "occupancy_sensors"
CONF_ILLUMINANCE: Final = "illuminance_sensor"
CONF_LUX_THRESHOLD: Final = "lux_threshold"
CONF_QUIET: Final = "quiet_entity"
CONF_BUTTON_IEEE: Final = "button_ieee"
CONF_BUTTON_COMMAND: Final = "button_command"
CONF_NIGHT_BRIGHTNESS: Final = "night_brightness"
CONF_NIGHT_KELVIN: Final = "night_kelvin"
CONF_AUTO_BRIGHTNESS: Final = "auto_brightness"
CONF_AUTO_KELVIN: Final = "auto_kelvin"
CONF_NIGHT_OFF_DELAY: Final = "night_off_delay"
CONF_AUTO_OFF_DELAY: Final = "auto_off_delay"
CONF_TRANSITION: Final = "transition"

DEFAULTS: Final = {
    CONF_LUX_THRESHOLD: 25.0,
    CONF_BUTTON_COMMAND: "off_press",
    CONF_NIGHT_BRIGHTNESS: 10.0,
    CONF_NIGHT_KELVIN: 2000,
    CONF_AUTO_BRIGHTNESS: 40.0,
    CONF_AUTO_KELVIN: 2700,
    CONF_NIGHT_OFF_DELAY: 1.0,
    CONF_AUTO_OFF_DELAY: 2.0,
    CONF_TRANSITION: 1.0,
}

STORAGE_VERSION: Final = 1
SAVE_DELAY_SECONDS: Final = 5
MEMORY_SETTLE_SECONDS: Final = 3  # manual mode must be this old before saving
MEMORY_DEBOUNCE_SECONDS: Final = 2  # wait for slider movements to end

EVENT_MODE_CHANGED: Final = f"{DOMAIN}_mode_changed"
