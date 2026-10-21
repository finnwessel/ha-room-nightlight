"""Config and options flow: one entry per room light."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import selector

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
)

OPTIONAL_KEYS = (CONF_LIGHTS, CONF_ILLUMINANCE, CONF_QUIET, CONF_BUTTON_IEEE)


def _number(minimum: float, maximum: float, step: float, unit: str | None = None) -> selector.NumberSelector:
    config = selector.NumberSelectorConfig(
        min=minimum, max=maximum, step=step, mode=selector.NumberSelectorMode.BOX
    )
    if unit is not None:  # None is rejected by the selector schema
        config["unit_of_measurement"] = unit
    return selector.NumberSelector(config)


def _entities(domain: str, *device_classes: str, multiple: bool = False) -> selector.EntitySelector:
    flt = selector.EntityFilterSelectorConfig(domain=domain)
    if device_classes:
        flt["device_class"] = [str(d) for d in device_classes]
    return selector.EntitySelector(selector.EntitySelectorConfig(filter=flt, multiple=multiple))


def _schema(defaults: dict[str, Any], with_name: bool) -> vol.Schema:
    def opt(key: str) -> vol.Optional:
        if defaults.get(key):
            return vol.Optional(key, description={"suggested_value": defaults[key]})
        return vol.Optional(key)

    def req(key: str) -> vol.Required:
        return vol.Required(key, default=defaults.get(key, DEFAULTS.get(key)))

    fields: dict[vol.Marker, Any] = {}
    if with_name:
        fields[vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, ""))] = str
    fields |= {
        (
            vol.Required(CONF_LIGHT, default=defaults[CONF_LIGHT])
            if defaults.get(CONF_LIGHT)
            else vol.Required(CONF_LIGHT)
        ): _entities("light"),
        opt(CONF_LIGHTS): _entities("light", multiple=True),
        vol.Required(CONF_OCCUPANCY, default=defaults.get(CONF_OCCUPANCY, [])): _entities(
            "binary_sensor",
            BinarySensorDeviceClass.MOTION,
            BinarySensorDeviceClass.OCCUPANCY,
            BinarySensorDeviceClass.PRESENCE,
            multiple=True,
        ),
        req(CONF_NIGHT_BRIGHTNESS): _number(0.1, 100, 0.1, "%"),
        req(CONF_NIGHT_KELVIN): _number(2000, 6500, 100, "K"),
        req(CONF_NIGHT_OFF_DELAY): _number(0.5, 60, 0.5, "min"),
        opt(CONF_ILLUMINANCE): _entities("sensor", SensorDeviceClass.ILLUMINANCE),
        req(CONF_LUX_THRESHOLD): _number(0, 2000, 1, "lx"),
        req(CONF_AUTO_BRIGHTNESS): _number(1, 100, 1, "%"),
        req(CONF_AUTO_KELVIN): _number(2000, 6500, 100, "K"),
        req(CONF_AUTO_OFF_DELAY): _number(0.5, 60, 0.5, "min"),
        opt(CONF_QUIET): _entities("input_boolean"),
        opt(CONF_BUTTON_IEEE): str,
        req(CONF_BUTTON_COMMAND): str,
        req(CONF_TRANSITION): _number(0, 10, 0.5, "s"),
    }
    return vol.Schema(fields)


def _validate(user_input: dict[str, Any]) -> dict[str, str]:
    errors: dict[str, str] = {}
    if not user_input.get(CONF_LIGHT):
        errors[CONF_LIGHT] = "no_light"
    if not user_input.get(CONF_OCCUPANCY):
        errors[CONF_OCCUPANCY] = "no_occupancy"
    return errors


def _clean(user_input: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in user_input.items() if v not in (None, "", []) and k != CONF_NAME}


class RoomNightLightConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create a room light."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                await self.async_set_unique_id(user_input[CONF_LIGHT])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={CONF_NAME: user_input[CONF_NAME]},
                    options=_clean(user_input),
                )
        return self.async_show_form(
            step_id="user", data_schema=_schema(user_input or {}, with_name=True), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> RoomNightLightOptionsFlow:
        return RoomNightLightOptionsFlow()


class RoomNightLightOptionsFlow(OptionsFlow):
    """Change a room light."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = _validate(user_input)
            if not errors:
                return self.async_create_entry(data=_clean(user_input))
        defaults = user_input or dict(self.config_entry.options)
        return self.async_show_form(
            step_id="init", data_schema=_schema(defaults, with_name=False), errors=errors
        )
