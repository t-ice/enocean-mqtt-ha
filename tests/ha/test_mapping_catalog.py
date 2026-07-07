"""The mapping catalog: factories produce the expected dicts/lists and return fresh objects.

(Value-identity of the whole MAPPING is checked separately by test_mapping.)
"""

from enocean2mqtt.homeassistant.mapping import _catalog as c


def test_temp_c_and_t_raw():
    assert c.temp_c() == {
        "component": "sensor",
        "name": "tempC",
        "config": {
            "state_topic": "",
            "device_class": "temperature",
            "state_class": "measurement",
            "unit_of_measurement": "°C",
            "value_template": "{{ value_json.TMP | round(1) }}",
        },
    }
    assert c.t_raw()["config"]["value_template"] == "{{ value_json.TMP }}"
    assert c.t_raw()["config"]["enabled_by_default"] == "false"


def test_energy_uses_template_constant():
    e = c.energy()
    assert e["component"] == "sensor" and e["name"] == "energy"
    assert e["config"]["value_template"] is c.TMPL_ENERGY
    assert c.TMPL_ENERGY.startswith("{% if value_json.UN == 0 %}")


def test_groups_compose_factories():
    assert c.temp_pair() == [c.t_raw(), c.temp_c()]
    names = [e["name"] for e in c.d2_metering()]
    assert names[:3] == ["switch", "energy", "power"] and names[-1] == "LC"
    assert [e["name"] for e in c.room_panel()][:3] == ["setpoint_type", "tempC", "hum"]


def test_factories_return_fresh_objects():
    # no two leaves may alias the same object
    assert c.temp_c() is not c.temp_c()
    assert c.temp_c()["config"] is not c.temp_c()["config"]
    a, b = c.temp_pair(), c.temp_pair()
    assert a is not b and a[0] is not b[0]
