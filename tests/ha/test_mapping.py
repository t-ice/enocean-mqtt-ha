"""The code-defined MAPPING has the expected entries and no orphans.

These tests guard the shape of ``MAPPING`` (``homeassistant/mapping/mapping.py``) directly.
"""

from enocean2mqtt.homeassistant.mapping import MAPPING
from enocean2mqtt.homeassistant.mapping.eep import (
    a5_hvac,
    a5_room_panels,
    a5_sensors,
    a5_weather,
    d2_devices,
    d2_switches,
    eltako,
    f6,
    misc,
)
from enocean2mqtt.protocol.profiles import PROFILES

_RORGS = (0xD2, 0xA5, 0xF6, 0xD5)
_FRAGMENTS = (
    a5_sensors,
    a5_room_panels,
    a5_hvac,
    a5_weather,
    d2_switches,
    d2_devices,
    f6,
    eltako,
    misc,
)
_COMPONENTS = {
    "sensor",
    "binary_sensor",
    "button",
    "switch",
    "number",
    "select",
    "light",
    "cover",
    "device_automation",
}


def _triples(mapping):
    """The set of leaf identities in a mapping fragment/dict: (rorg,func,type) + string keys."""
    ids = set()
    for key, sub in mapping.items():
        if isinstance(key, int):
            for func, types in sub.items():
                ids.update((key, func, typ) for typ in types)
        else:
            ids.add(key)
    return ids


def test_fragment_merge_lossless():
    """The 9 fragments carry disjoint leaves that together form exactly the merged MAPPING."""
    owner: dict = {}
    for frag in _FRAGMENTS:
        for ident in _triples(frag.MAPPING):
            assert ident not in owner, f"{ident} in both {owner[ident]} and {frag.__name__}"
            owner[ident] = frag.__name__
    assert set(owner) == _triples(MAPPING)


def test_mapping_leaves_wellformed():
    """Every EEP leaf has a device_config + a non-empty list of valid {component,name,config}."""
    for rorg in _RORGS:
        for func, types in MAPPING.get(rorg, {}).items():
            for typ, leaf in types.items():
                where = f"{rorg:#04x}-{func:#04x}-{typ:#04x}"
                assert "device_config" in leaf, f"{where}: no device_config"
                assert isinstance(leaf.get("entities"), list) and leaf["entities"], (
                    f"{where}: entities"
                )
                for e in leaf["entities"] + leaf.get("virtual", []):
                    assert {"component", "name", "config"} <= set(e), f"{where}: entity keys"
                    assert e["component"] in _COMPONENTS, f"{where}: bad component {e['component']}"
                    assert isinstance(e["config"], dict), f"{where}: config not a dict"


def test_every_mapping_triple_has_a_decodable_profile():
    """No orphan entities: every RORG-FUNC-TYPE in MAPPING is a profile the engine can decode."""
    for rorg in _RORGS:
        for func, types in MAPPING.get(rorg, {}).items():
            for type_ in types:
                key = (rorg, func, type_)
                assert key in PROFILES, f"orphan mapping {rorg:02X}-{func:02X}-{type_:02X}"


def test_mapping_spot_check_a5_06_03():
    # A5-06-03: skip LRNB; SVC -> voltage sensor, ILL -> illuminance sensor.
    entry = MAPPING[0xA5][0x06][0x03]
    by_name = {e["name"]: e for e in entry["entities"]}
    assert "lrnb" not in by_name
    assert by_name["svc"]["component"] == "sensor"
    assert by_name["svc"]["config"]["device_class"] == "voltage"
    assert by_name["svc"]["config"]["unit_of_measurement"] == "V"
    assert by_name["ill"]["config"]["device_class"] == "illuminance"
    assert by_name["ill"]["config"]["unit_of_measurement"] == "lx"
    assert by_name["ill"]["config"]["value_template"] == "{{ value_json.ILL }}"


def test_tf61d_aliases_fud14():
    """TF61D is an Eltako dimmer on the same A5-38-08 protocol → identical mapping to fud14."""
    eltako = MAPPING["eltako"]
    assert "tf61d" in eltako
    assert eltako["tf61d"] == eltako["fud14"]


def test_d2_01_11_has_a_switch_entity():
    """The Omnio D2-01-11 actuator (added 0.9.1) is mapped to a controllable switch."""
    entry = MAPPING[0xD2][0x01][0x11]
    assert any(e["component"] == "switch" for e in entry["entities"])
