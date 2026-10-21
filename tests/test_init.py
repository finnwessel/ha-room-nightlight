"""Home Assistant tests: config flow and a night in the kitchen."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.room_nightlight.const import (
    CONF_BUTTON_IEEE,
    CONF_LIGHT,
    CONF_LIGHTS,
    CONF_NAME,
    CONF_OCCUPANCY,
    DOMAIN,
)

LIGHT = "light.kitchen_ambilight"
MOTION = "binary_sensor.kitchen_motion"
IEEE = "00:17:88:01:0e:d5:1f:ec"


def _states(hass: HomeAssistant) -> None:
    hass.states.async_set(LIGHT, "off", {"supported_color_modes": ["color_temp"]})
    hass.states.async_set(MOTION, "off", {"device_class": "occupancy"})
    hass.states.async_set("sun.sun", "below_horizon")


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Kitchen",
        data={CONF_NAME: "Kitchen"},
        options={
            CONF_LIGHT: LIGHT,
            CONF_LIGHTS: [LIGHT],
            CONF_OCCUPANCY: [MOTION],
            CONF_BUTTON_IEEE: IEEE,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


def _mode_entity(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    entity_id = er.async_get(hass).async_get_entity_id("select", DOMAIN, f"{entry.entry_id}_mode")
    assert entity_id is not None
    return entity_id


async def test_user_flow(hass: HomeAssistant) -> None:
    _states(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_NAME: "Kitchen", CONF_LIGHT: LIGHT, CONF_OCCUPANCY: [MOTION]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"][CONF_LIGHT] == LIGHT
    assert result["options"]["night_brightness"] == 10.0
    await hass.async_block_till_done()


async def test_user_flow_requires_sensor(hass: HomeAssistant) -> None:
    _states(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_NAME: "Kitchen", CONF_LIGHT: LIGHT, CONF_OCCUPANCY: []}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_OCCUPANCY: "no_occupancy"}


async def test_night_in_the_kitchen(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    _states(hass)
    turn_on = async_mock_service(hass, "light", "turn_on")
    turn_off = async_mock_service(hass, "light", "turn_off")
    entry = await _setup(hass)
    mode = _mode_entity(hass, entry)
    assert hass.states.get(mode).state == "off"

    # Motion at night → night light 10 % / 2000 K
    hass.states.async_set(MOTION, "on", {"device_class": "occupancy"})
    await hass.async_block_till_done()
    assert hass.states.get(mode).state == "night"
    assert turn_on[-1].data["brightness"] == 26
    assert turn_on[-1].data["color_temp_kelvin"] == 2000

    # The light reports on (our own action) → stays night
    hass.states.async_set(LIGHT, "on", {"brightness": 26})
    await hass.async_block_till_done()
    assert hass.states.get(mode).state == "night"

    # One minute without motion → off
    hass.states.async_set(MOTION, "off", {"device_class": "occupancy"})
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(mode).state == "off"
    assert turn_off[-1].data["entity_id"] == LIGHT
    hass.states.async_set(LIGHT, "off")
    await hass.async_block_till_done()

    # Button → manual with default normal state
    hass.bus.async_fire("zha_event", {"device_ieee": IEEE, "command": "off_press"})
    await hass.async_block_till_done()
    assert hass.states.get(mode).state == "manual"
    assert turn_on[-1].data["brightness"] == 255

    # Switched off in the app → off
    hass.states.async_set(LIGHT, "on", {"brightness": 255})
    await hass.async_block_till_done()
    hass.states.async_set(LIGHT, "off")
    await hass.async_block_till_done()
    assert hass.states.get(mode).state == "off"

    # Switched on in the app → manual, motion does nothing then
    hass.states.async_set(LIGHT, "on", {"brightness": 100})
    await hass.async_block_till_done()
    assert hass.states.get(mode).state == "manual"

    # Selecting a mode runs it
    await hass.services.async_call(
        "select", "select_option", {"entity_id": mode, "option": "night"}, blocking=True
    )
    assert hass.states.get(mode).state == "night"


async def test_motion_switch_pauses_automation(hass: HomeAssistant) -> None:
    _states(hass)
    async_mock_service(hass, "light", "turn_on")
    entry = await _setup(hass)
    switch = er.async_get(hass).async_get_entity_id("switch", DOMAIN, f"{entry.entry_id}_motion")
    await hass.services.async_call("switch", "turn_off", {"entity_id": switch}, blocking=True)
    hass.states.async_set(MOTION, "on", {"device_class": "occupancy"})
    await hass.async_block_till_done()
    assert hass.states.get(_mode_entity(hass, entry)).state == "off"
