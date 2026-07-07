"""The Sensor value object is a typed, dict-compatible drop-in for the legacy sensor dict."""

from enocean2mqtt.domain.sensor import Sensor


def test_dict_semantics_membership_get_set_del():
    s = Sensor(name="e2m/x", rorg=0xA5, func=0x13, type=0x01)
    # membership reflects ACTUAL presence (the encoder/inbound rely on this)
    assert "rorg" in s
    assert "raw_data" not in s
    assert s.get("missing") is None and s.get("missing", 7) == 7
    s["raw_data"] = "01:00:00:09"
    assert "raw_data" in s and s["raw_data"] == "01:00:00:09"
    del s["raw_data"]
    assert "raw_data" not in s


def test_typed_attribute_reads():
    s = Sensor(name="e2m/x", rorg=0xA5, func=0x13, type=0x01, address=0x059ED79A)
    assert s.rorg == 0xA5 and s.func == 0x13 and s.type == 0x01
    assert s.address == 0x059ED79A and s.name == "e2m/x"
    # absent typed fields read as None (not KeyError)
    assert s.sender is None and s.model is None and s.raw_data is None
    assert s.learn is False


def test_equals_plain_dict_so_loader_tests_stay_green():
    s = Sensor(name="e2m/x", address=1, rorg=0xF6, func=2, type=1)
    assert s == {"name": "e2m/x", "address": 1, "rorg": 0xF6, "func": 2, "type": 1}
    assert [s] == [{"name": "e2m/x", "address": 1, "rorg": 0xF6, "func": 2, "type": 1}]


def test_from_dict_roundtrip_and_idempotent():
    d = {"name": "e2m/x", "sender": 0xFFAE7C90, "model": "eltako/FSR14"}
    s = Sensor.from_dict(d)
    assert s.to_dict() == d
    assert Sensor.from_dict(s) is s  # already a Sensor → unchanged


def test_runtime_data_accumulation_like_inbound():
    s = Sensor(name="e2m/x")
    if "data" not in s:
        s["data"] = {}
    s["data"]["DB1"] = 1
    assert s.data == {"DB1": 1}
