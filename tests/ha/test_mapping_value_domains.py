"""HA templates must read decoded fields the way the decoder actually publishes them.

The window-handle bug fixed in 1.0.9 and the two found by the audit after it (A5-20-04 room
temperature / failure codes, A5-13-06 position) are one bug class: a template written for raw
values while the decoder publishes scaled ones (or the reverse). ``test_mapping_profile_fields``
only checks that a referenced field exists; these tests check the *values*:

1. Every literal a template compares a field against (``==``, ``!=``, ``in``, ``<``, …) must be a
   value the engine can publish for that field — computed by running the real engine over every
   raw value of the field, not from the profile metadata.
2. No template may re-apply a field's scaling: dividing a field the decoder already scales by its
   raw maximum (``/ 255``, ``/ 4095`` …) scales it twice.
3. A temperature sensor that keeps its last state must not truncate it with ``| int``.

Plus end-to-end regressions: decode a real telegram, render the template, check the reading.
"""

from __future__ import annotations

import dataclasses
import math
import numbers
import re

import pytest

import enocean2mqtt.protocol.utils as u
from enocean2mqtt.application.decoder import PacketDecoder
from enocean2mqtt.domain.sensor import Sensor
from enocean2mqtt.homeassistant.mapping import MAPPING
from enocean2mqtt.protocol.packet import RadioPacket
from enocean2mqtt.protocol.profiles import PROFILES
from enocean2mqtt.protocol.profiles.engine import _decode_field

_FIELD = r"value_json(?:\.(?P<dot>[A-Za-z_][A-Za-z0-9_]*)|\[['\"](?P<key>[^'\"]+)['\"]\])"
_FILTER = r"\s*(?:\|\s*(?:int|float)(?:\([^)]*\))?\s*)?"
_COMPARE = re.compile(_FIELD + _FILTER + r"(?P<op>==|!=|<=|>=|<|>)\s*(?P<num>-?\d+(?:\.\d+)?)\b")
_IN = re.compile(_FIELD + _FILTER + r"(?:not\s+)?in\s*[\(\[](?P<items>[-\d.,\s]+)[\)\]]")
_MAX_ENUMERATED_BITS = 16


def _leaves(obj, path=()):
    if isinstance(obj, dict):
        if "entities" in obj:
            yield path, obj
        for key, value in obj.items():
            if key != "entities":
                yield from _leaves(value, (*path, key))


def _templates(entity):
    for key, value in entity.get("config", {}).items():
        if isinstance(value, str) and "value_json" in value:
            yield key, value


def _eep_leaves():
    """(eep label, profile, entity) for every mapping entity of an EEP that has a profile."""
    for rorg, funcs in MAPPING.items():
        if not isinstance(rorg, int):  # 'eltako' / 'common' / 'system' carry no single EEP
            continue
        for func, types in funcs.items():
            for typ, sub in types.items():
                profile = PROFILES.get((rorg, func, typ))
                if profile is None:
                    continue
                for _path, leaf in _leaves(sub):
                    for entity in leaf["entities"]:
                        yield f"{rorg:02X}-{func:02X}-{typ:02X}", profile, entity


def _published_values(profile, shortcut):
    """Every value the decoder can publish for *shortcut* (None if too wide to enumerate)."""
    values = set()
    for case in profile.cases:
        for field in case.fields:
            if field.shortcut != shortcut:
                continue
            if field.size > _MAX_ENUMERATED_BITS:
                return None
            at_zero = dataclasses.replace(field, offset=0)
            for raw in range(2**field.size):
                decoded = _decode_field(at_zero, u.to_bitarray(raw, field.size))
                value = decoded["value"]
                values.add(value if isinstance(value, numbers.Number) else decoded["raw_value"])
    return values or None


def _producible(values, number, op):
    if op in ("==", "!="):
        return any(math.isclose(float(v), number, abs_tol=1e-6) for v in values)
    low, high = min(values), max(values)
    return low - 1e-6 <= number <= high + 1e-6  # an ordering test inside the range can be true


def _comparisons():
    for eep, profile, entity in _eep_leaves():
        for key, template in _templates(entity):
            for match in _COMPARE.finditer(template):
                field = match["dot"] or match["key"]
                yield eep, profile, entity["name"], key, field, match["op"], float(match["num"])
            for match in _IN.finditer(template):
                field = match["dot"] or match["key"]
                for item in re.findall(r"-?\d+(?:\.\d+)?", match["items"]):
                    yield eep, profile, entity["name"], key, field, "==", float(item)


def test_every_compared_value_can_actually_be_published():
    impossible = []
    for eep, profile, name, key, field, op, number in _comparisons():
        values = _published_values(profile, field)
        if values is None:  # not decoded here (other test) or a field too wide to enumerate
            continue
        if not _producible(values, number, op):
            impossible.append(f"{eep} {name}.{key}: {field} {op} {number:g}")
    assert not impossible, "templates compare against values the decoder never publishes:\n" + (
        "\n".join(sorted(set(impossible)))
    )


def _decoder_scaled_fields(profile):
    """{shortcut: raw maximum} for fields the decoder publishes already scaled."""
    scaled = {}
    for case in profile.cases:
        for f in case.fields:
            if not f.shortcut:
                continue
            bounds = (f.range_min, f.range_max, f.scale_min, f.scale_max)
            if f.kind == "value" and None not in bounds:
                if (f.range_min, f.range_max) != (f.scale_min, f.scale_max):
                    scaled[f.shortcut] = int(f.range_max)
            elif f.kind == "enum":
                for item in f.items:
                    if item.scale_min is not None and item.max is not None:
                        scaled[f.shortcut] = int(item.max)
    return scaled


def test_no_template_scales_a_field_twice():
    doubled = []
    for eep, profile, entity in _eep_leaves():
        scaled = _decoder_scaled_fields(profile)
        for key, template in _templates(entity):
            for expression in re.findall(r"\{\{(.*?)\}\}", template, flags=re.S):
                for match in re.finditer(_FIELD, expression):
                    field = match["dot"] or match["key"]
                    raw_max = scaled.get(field)
                    if raw_max and re.search(rf"/\s*{raw_max}(?:\.0)?\b", expression):
                        doubled.append(f"{eep} {entity['name']}.{key}: {field} ÷ {raw_max}")
    assert not doubled, "templates re-scale a field the decoder already scales:\n" + (
        "\n".join(sorted(set(doubled)))
    )


def test_kept_temperatures_are_not_truncated():
    truncating = [
        f"{eep} {entity['name']}"
        for eep, _profile, entity in _eep_leaves()
        if entity.get("config", {}).get("device_class") == "temperature"
        and "states(entity_id)|int" in entity["config"].get("value_template", "")
    ]
    assert not truncating, f"temperature keeps its last state as an integer: {truncating}"


# --- end to end: real telegram → decoder → template ------------------------------------------


def _render(rorg, func, typ, name, payload, previous="21.4"):
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment()
    env.globals["states"] = lambda _entity_id: previous  # the entity's current HA state
    entity = next(e for e in MAPPING[rorg][func][typ]["entities"] if e["name"] == name)
    template = entity["config"]["value_template"]
    return env.from_string(template).render(value_json=payload, entity_id="sensor.x").strip()


def _decode(rorg, func, typ, db, direction=None):
    sensor = Sensor.from_dict(
        {"name": "t", "address": 1, "rorg": rorg, "func": func, "type": typ, "direction": direction}
    )
    packet = RadioPacket(
        1, data=[rorg, *db, 1, 2, 3, 4, 0], optional=[1, 0xFF, 0xFF, 0xFF, 0xFF, 60, 0]
    )
    return PacketDecoder.decode(packet, sensor)


@pytest.mark.parametrize(("raw", "celsius"), [(0, 10.0), (128, 20.0), (255, 30.0)])
def test_a5_20_04_room_temperature(raw, celsius):
    payload = _decode(0xA5, 0x20, 0x04, [50, 100, raw, 0x08], direction=1)  # FL = 0
    assert payload["TMPFC"] == pytest.approx(celsius, abs=0.05)
    assert float(_render(0xA5, 0x20, 0x04, "room_temperature", payload)) == pytest.approx(
        celsius, abs=0.05
    )


@pytest.mark.parametrize(
    ("code", "entity"),
    [
        (17, "err_meas"),
        (18, "battery"),
        (20, "err_frost_prot"),
        (33, "err_blocked_valve"),
        (36, "err_endpoint"),
        (40, "err_novalve"),
    ],
)
def test_a5_20_04_failure_codes(code, entity):
    payload = _decode(0xA5, 0x20, 0x04, [50, 100, code, 0x09], direction=1)  # FL = 1
    assert payload["TMPFC"] == code
    assert _render(0xA5, 0x20, 0x04, entity, payload) == "ON"
    assert _render(0xA5, 0x20, 0x04, "failure", payload) == "ON"
    # a failure telegram keeps the last room temperature, decimals included
    assert _render(0xA5, 0x20, 0x04, "room_temperature", payload) == "21.4"


def test_a5_20_04_other_failure_code_leaves_the_rest_off():
    payload = _decode(0xA5, 0x20, 0x04, [50, 100, 18, 0x09], direction=1)
    assert _render(0xA5, 0x20, 0x04, "err_meas", payload) == "OFF"


def test_a5_13_06_position():
    # 38.44° N = 12-bit 0xB6A (MSB 0xB, LSB 0x6A); 12.79° E = 0x891 (MSB 0x8, LSB 0x91); ID 6.
    payload = _decode(0xA5, 0x13, 0x06, [0xB8, 0x6A, 0x91, 0x68])
    assert payload["LAT(LSB)"] == 0x6A and payload["LOT(LSB)"] == 0x91  # raw halves
    latitude = float(_render(0xA5, 0x13, 0x06, "latitude", payload))
    longitude = float(_render(0xA5, 0x13, 0x06, "longitude", payload))
    assert latitude == pytest.approx(0xB6A * 180 / 4095 - 90, abs=1e-6)
    assert longitude == pytest.approx(0x891 * 360 / 4095 - 180, abs=1e-6)


def test_a5_13_01_id6_and_a5_13_06_decode_the_position_alike():
    """The multi-telegram weather profile (A5-13-01, ID 6) already decoded it raw — consistent."""
    db = [0xB8, 0x6A, 0x91, 0x68]
    a = _decode(0xA5, 0x13, 0x06, db)
    b = _decode(0xA5, 0x13, 0x01, db)
    for key in ("LAT(MSB)", "LOT(MSB)", "LAT(LSB)", "LOT(LSB)"):
        assert a[key] == b[key]
