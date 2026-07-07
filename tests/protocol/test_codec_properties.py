"""Property-style round-trip sweep for the EEP codec: for every linear value field of a set of
representative profiles, encoding a swept physical value and decoding it back preserves the value to
within one raw step (int-truncation of the inverse scale). A denser, generated complement to the
certification-vector round-trip in test_engine_encode.py — no external property-test dependency."""

import pytest

from enocean2mqtt.protocol import utils as u
from enocean2mqtt.protocol.eep_codec import EepCodec
from enocean2mqtt.protocol.profiles.engine import find_profile

# (rorg, func, type, payload_bytes) — 4BS profiles with linear value fields.
_PROFILES = [
    (0xA5, 0x02, 0x05, 4),  # temperature 0..40 C (inverted scale)
    (0xA5, 0x04, 0x01, 4),  # humidity + temperature
    (0xA5, 0x10, 0x12, 4),  # room panel: set point + humidity + temperature
    (0xA5, 0x10, 0x06, 4),  # room panel: set point + temperature (inverted)
    (0xA5, 0x05, 0x01, 4),  # barometric 500..1150 hPa (10-bit)
]


def _linear_value_fields(rorg, func, type_):
    case = find_profile(rorg, func, type_).cases[0]
    return [
        f
        for f in case.fields
        if f.kind == "value"
        and None not in (f.range_min, f.range_max, f.scale_min, f.scale_max)
        and f.range_max != f.range_min
    ]


def _sweep_cases():
    for rorg, func, type_, nbytes in _PROFILES:
        for field in _linear_value_fields(rorg, func, type_):
            yield pytest.param(
                rorg,
                func,
                type_,
                nbytes,
                field,
                id=f"{rorg:02X}-{func:02X}-{type_:02X}:{field.shortcut}",
            )


@pytest.mark.parametrize("rorg,func,type_,nbytes,field", list(_sweep_cases()))
def test_value_field_roundtrips_across_its_range(rorg, func, type_, nbytes, field):
    codec = EepCodec()
    assert codec.select(rorg, func, type_)

    lo, hi = sorted((field.scale_min, field.scale_max))
    step = abs((field.scale_max - field.scale_min) / (field.range_max - field.range_min))
    tol = step * 1.01 + 1e-6  # one raw LSB, per the encode int() truncation

    for i in range(11):  # sweep the whole physical range
        value = lo + (hi - lo) * i / 10
        bd, bs = codec.encode(
            {field.shortcut: value}, u.to_bitarray([0] * nbytes, 8 * nbytes), u.to_bitarray([0], 8)
        )
        got = codec.decode(bd, bs)[field.shortcut]["value"]
        assert abs(got - value) <= tol, f"{field.shortcut}: {got} vs {value} (tol {tol})"
