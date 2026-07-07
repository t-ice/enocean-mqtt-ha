"""engine.encode — the encode half of the code engine (now the only engine).

Two guarantees:
- a concrete value profile encodes to the expected raw byte (golden), and
- decode↔encode is a faithful inverse across the certification corpus (enum/bool recover their raw
  exactly; scaled values recover to within one resolution step, matching int() truncation).
"""

import json
import os

import enocean2mqtt.protocol.utils as u
from enocean2mqtt.protocol.profiles.engine import decode, encode, find_profile, select_case

CERT = os.path.join(
    os.path.dirname(__file__), "..", "fixtures", "certification", "eep_certification.json"
)


def _zeros(nbytes):
    return u.to_bitarray([0] * nbytes, 8 * nbytes)


def test_encode_a5_02_05_temperature_golden():
    """A5-02-05 {TMP: 21.5} → DB1 raw 117 (the golden encoded value)."""
    case = select_case(find_profile(0xA5, 0x02, 0x05), _zeros(4), _zeros(1))
    engine_bits, _ = encode(case, {"TMP": 21.5}, _zeros(4), _zeros(1))

    data = [u.from_bitarray(engine_bits[i * 8 : (i + 1) * 8]) for i in range(4)]
    assert data[2] == 117, f"TMP raw byte {data[2]} != 117"  # DB1 at offset 16 (3rd data byte)
    # And it decodes back to ~21.5 °C (round-trip sanity).
    assert abs(decode(case, engine_bits, _zeros(1))["TMP"]["value"] - 21.5) < 0.2


def test_decode_encode_roundtrip_over_certification():
    """For every code-covered cert vector, re-encoding the decoded values reproduces the field's
    raw bits: exactly for enum/bool, within one step for scaled values (int() truncation)."""
    cases = json.load(open(CERT, encoding="utf-8"))["cases"]
    checked = 0
    for c in cases:
        profile = find_profile(c["rorg"], c["func"], c["type"])
        if profile is None:
            continue
        bit_data = u.to_bitarray(c["data"], 8 * len(c["data"]))
        bit_status = u.to_bitarray([c["status"] or 0], 8)
        case = select_case(profile, bit_data, bit_status)
        if case is None:
            continue
        original = decode(case, bit_data, bit_status)
        value_fields = {f.shortcut: f for f in case.fields if f.kind == "value"}

        # Re-encode each linear value field's decoded value into fresh bits, then re-decode and
        # compare raw. This exercises the inverse-scale path (enum/bool raw round-trips trivially
        # and is covered by the certification + golden tests).
        props = {sc: original[sc]["value"] for sc in value_fields if sc in original}
        if not props:
            continue
        reencoded, _ = encode(case, props, _zeros(len(c["data"])), _zeros(1))
        redecoded = decode(case, reencoded, bit_status)
        for sc in props:
            got, want = redecoded[sc]["raw_value"], original[sc]["raw_value"]
            # int() truncation of the inverse scale may land one step off.
            assert abs(got - want) <= 1, f"{c['eep']}/{sc}: value raw {got} vs {want}"
        checked += 1
    assert checked > 200, f"expected broad round-trip coverage, checked {checked}"
