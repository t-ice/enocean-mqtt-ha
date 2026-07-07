"""Unit tests for the mapping factories: each returns the exact expected dict."""

from enocean2mqtt.homeassistant.mapping import _builders as b


def test_enum_map_template_sources_labels_from_profile():
    # fan-mode labels come from the D2-11-01 profile's FS enum items (single source of truth)
    fs = b.enum_map_template(0xD2, 0x11, 0x01, "FS")
    assert fs.startswith("{% set m = {0: 'Auto', 1: 'Speed 0',")
    assert "7: 'n/a'" in fs
    assert fs.endswith("{{ m.get(value_json.FS | int, value_json.FS) }}")
    spt = b.enum_map_template(0xD2, 0x11, 0x01, "SPT")
    assert "temperature correction" in spt and "value_json.SPT" in spt


def test_dcfg_defaults_and_overrides():
    assert b.dcfg() == {
        "command": "",
        "channel": "",
        "log_learn": "",
        "direction": "",
        "answer": "",
    }
    assert b.dcfg(command="CMD", channel="CMD")["command"] == "CMD"
    # fresh object each call (no shared aliasing between leaves)
    assert b.dcfg() is not b.dcfg()


def test_dcfg_gw():
    assert b.dcfg_gw("0xA5", "0x38", "0x08") == [
        {
            "rorg": "0xA5",
            "func": "0x38",
            "type": "0x08",
            "command": "",
            "channel": "",
            "log_learn": "",
            "direction": "",
            "answer": "",
        }
    ]
    assert b.dcfg_gw("0xA5", "0x3F", "0x7F", channel="DT")[0]["channel"] == "DT"


def test_vt():
    assert b.vt("TMP") == "{{ value_json.TMP }}"
    assert b.vt("TMP", "round(1)") == "{{ value_json.TMP | round(1) }}"


def test_entity_generic():
    assert b.entity("cover", "cover", command_topic="req", payload_open="UP") == {
        "component": "cover",
        "name": "cover",
        "config": {"command_topic": "req", "payload_open": "UP"},
    }


def test_sensor_only_emits_provided_optionals():
    assert b.sensor("t_raw", b.vt("TMP"), state_class="measurement") == {
        "component": "sensor",
        "name": "t_raw",
        "config": {
            "state_topic": "",
            "state_class": "measurement",
            "value_template": "{{ value_json.TMP }}",
        },
    }
    full = b.sensor(
        "tempC",
        b.vt("TMP", "round(1)"),
        device_class="temperature",
        state_class="measurement",
        unit="°C",
        icon="mdi:x",
        enabled_by_default=False,
    )
    assert full["config"] == {
        "state_topic": "",
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": "°C",
        "icon": "mdi:x",
        "enabled_by_default": False,
        "value_template": "{{ value_json.TMP | round(1) }}",
    }


def test_binary_only_emits_provided_optionals():
    assert b.binary(
        "occ", "{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}", device_class="occupancy"
    ) == {
        "component": "binary_sensor",
        "name": "occ",
        "config": {
            "state_topic": "",
            "device_class": "occupancy",
            "value_template": "{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}",
        },
    }
    assert b.binary("lc", b.vt("LC"), payload_on="on", payload_off="off")["config"] == {
        "state_topic": "",
        "payload_on": "on",
        "payload_off": "off",
        "value_template": "{{ value_json.LC }}",
    }
