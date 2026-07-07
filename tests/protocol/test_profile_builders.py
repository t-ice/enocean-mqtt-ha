"""Unit tests for the EEP profile builder helpers (_build)."""

from enocean2mqtt.protocol.profiles import _build as b
from enocean2mqtt.protocol.profiles._model import Case, Condition, EnumItem, Field, Profile


def test_field_defaults_and_options():
    f = b.field("TMP", "Temperature", 16, 8, "value", unit="°C", scale_min=-40.0, scale_max=0.0)
    assert isinstance(f, Field)
    assert (f.shortcut, f.offset, f.size, f.kind, f.unit) == ("TMP", 16, 8, "value", "°C")
    assert (f.scale_min, f.scale_max) == (-40.0, 0.0)
    assert f.range_min is None and f.items == () and f.fixed_value is None


def test_enum_maps_minimum_maximum_to_model():
    assert b.enum("Data telegram", 1) == EnumItem(description="Data telegram", value=1)
    r = b.enum("range", minimum=0, maximum=250, scale_min=0.0, scale_max=100.0)
    assert (r.min, r.max, r.scale_min, r.scale_max) == (0, 250, 0.0, 100.0)


def test_case_profile_cond():
    c = b.cond("data", 0, 3, 2)
    assert isinstance(c, Condition) and (c.source, c.offset, c.size, c.value) == ("data", 0, 3, 2)
    case = b.case((b.LRNB_4BS,), conditions=(c,))
    assert isinstance(case, Case) and case.conditions == (c,) and len(case.fields) == 1
    p = b.profile(0xA5, 0x02, 0x01, "Temp", case)
    assert isinstance(p, Profile) and (p.rorg, p.func, p.type) == (0xA5, 0x02, 0x01)
    assert p.cases == (case,)


def test_lrnb_4bs_shared_field():
    assert b.LRNB_4BS.shortcut == "LRNB" and b.LRNB_4BS.offset == 28 and b.LRNB_4BS.size == 1
    assert [it.description for it in b.LRNB_4BS.items] == ["Teach-in telegram", "Data telegram"]
