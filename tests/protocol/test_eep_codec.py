"""EepCodec: the EEP-interpretation seam split out of the ESP3 Packet (M3)."""

from enocean2mqtt.protocol import utils as u
from enocean2mqtt.protocol.constants import RORG
from enocean2mqtt.protocol.eep_codec import EepCodec
from enocean2mqtt.protocol.profiles import PROFILES, ProfileRegistry


def _bits(data_bytes):
    return u.to_bitarray(data_bytes, 8 * len(data_bytes))


def test_select_known_profile_then_decode():
    codec = EepCodec()
    assert codec.select(RORG.BS4, 0x02, 0x05) is True  # A5-02-05 temperature
    # DB1 = 0xFF encodes 0.0 C (inverted scale); the codec decodes it via the selected profile.
    decoded = codec.decode(_bits([0x00, 0x00, 0xFF, 0x08]), _bits([0x00]))
    assert decoded["TMP"]["value"] == 0.0


def test_select_unknown_profile_is_falsey_and_decodes_to_empty():
    codec = EepCodec()
    assert codec.select(RORG.BS4, 0x7E, 0x7E) is False  # no such profile
    assert codec.decode(_bits([0, 0, 0, 0]), _bits([0])) == {}
    # encode is a no-op without a case: the bits pass through unchanged.
    bd, bs = _bits([1, 2, 3, 4]), _bits([0])
    assert codec.encode({"TMP": 20.0}, bd, bs) == (bd, bs)


def test_encode_roundtrips_through_select():
    codec = EepCodec()
    codec.select(RORG.BS4, 0x02, 0x05)
    bd, bs = codec.encode({"TMP": 21.5}, _bits([0, 0, 0, 0]), _bits([0]))
    # re-decoding the freshly-encoded bits recovers ~21.5 C
    assert abs(codec.decode(bd, bs)["TMP"]["value"] - 21.5) < 0.2


def test_injected_registry_is_used():
    # A registry limited to a single profile: the codec finds it but nothing else.
    only_temp = ProfileRegistry({(0xA5, 0x02, 0x05): PROFILES[(0xA5, 0x02, 0x05)]})
    codec = EepCodec(registry=only_temp)
    assert codec.select(RORG.BS4, 0x02, 0x05) is True
    assert codec.select(RORG.BS4, 0x10, 0x03) is False  # present in the default set, absent here
