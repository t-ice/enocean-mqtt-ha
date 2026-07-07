"""Structural invariants for the assembled PROFILES and a lossless split-merge check.

These replace the old repr snapshot: instead of pinning the whole blob, they assert the properties
that must hold (no fragment collision, every profile well-formed). Decode *correctness* is proven by
``test_certification`` (official vectors) and the family decode tests.
"""

from enocean2mqtt.protocol.profiles import PROFILES
from enocean2mqtt.protocol.profiles.eep import (
    a5_hvac,
    a5_room_panels,
    a5_sensors,
    a5_weather,
    d2_devices,
    d2_switches,
    f6,
)

_FRAGMENTS = (a5_sensors, a5_room_panels, a5_hvac, a5_weather, d2_switches, d2_devices, f6)
_KINDS = {"value", "enum", "bool", "raw", "fixed"}


def test_fragment_merge_lossless():
    """Fragment keys are disjoint and together form exactly PROFILES (no silent overwrite)."""
    owner: dict[tuple[int, int, int], str] = {}
    for frag in _FRAGMENTS:
        for key in frag.PROFILES:
            assert key not in owner, f"{key} defined in both {owner[key]} and {frag.__name__}"
            owner[key] = frag.__name__
    assert set(owner) == set(PROFILES)
    assert sum(len(f.PROFILES) for f in _FRAGMENTS) == len(PROFILES)


def test_profiles_wellformed():
    for key, p in PROFILES.items():
        assert key == (p.rorg, p.func, p.type), f"key/attr mismatch for {key}"
        for case in p.cases:
            for c in case.conditions:
                assert c.source in {"data", "status"}, f"{key}: bad condition source {c.source}"
            for f in list(case.fields) + list(case.status_fields):
                assert f.kind in _KINDS, f"{key} {f.shortcut!r}: unknown kind {f.kind!r}"
                assert f.offset >= 0 and f.size > 0, f"{key} {f.shortcut!r}: bad offset/size"
                if f.kind == "enum":
                    assert f.items, f"{key} {f.shortcut!r}: enum field without items"
                if f.kind == "fixed":
                    assert f.fixed_value is not None, f"{key} {f.shortcut!r}: fixed without value"
