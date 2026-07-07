"""A5-10-03/06 keep the raw setpoint (0-255) AND expose a scaled °C setpoint_c (SP*40/255).

Raw is preserved so existing thermostat-identification automations keep working; the °C sensor is
additive (Eltako setpoint is 0-255 → 0-40 °C).
"""

from enocean2mqtt.homeassistant.mapping import MAPPING


def _sensors(func, type_):
    return {
        e["name"]: e for e in MAPPING[0xA5][func][type_]["entities"] if e["component"] == "sensor"
    }


def test_room_and_heating_have_raw_and_scaled_setpoint():
    for type_ in (0x03, 0x06):
        s = _sensors(0x10, type_)
        assert "setpoint" in s, f"A5-10-{type_:02X}: raw setpoint missing"
        assert s["setpoint"]["config"]["value_template"] == "{{ value_json.SP }}"  # raw, unchanged
        sc = s["setpoint_c"]["config"]
        assert "40 / 255" in sc["value_template"]
        assert sc["unit_of_measurement"] == "°C"
        assert sc["device_class"] == "temperature"


def test_scaling_formula_matches_examples():
    # mirrors the mapping template SP*40/255 rounded to 1 dp (your live values 76/128/178)
    def to_c(sp):
        return round(sp * 40 / 255, 1)

    assert (to_c(76), to_c(128), to_c(178)) == (11.9, 20.1, 27.9)
