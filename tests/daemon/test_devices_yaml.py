"""devices.yaml loader + device validation."""

import textwrap

import pytest

from enocean2mqtt.devices import (
    device_to_sensor,
    duplicate_addresses,
    duplicate_senders,
    eep_to_rft,
    load_devices_yaml,
)


def test_duplicate_senders():
    sensors = [
        {"name": "A", "sender": 0xFFAE7C81},
        {"name": "B", "sender": 0xFFAE7C81},  # clash with A
        {"name": "C", "sender": 0xFFAE7C82},
        {"name": "D"},  # no sender
    ]
    dups = duplicate_senders(sensors)
    assert dups == {0xFFAE7C81: ["A", "B"]}


def test_eep_to_rft():
    assert eep_to_rft("A5-13-01") == (0xA5, 0x13, 0x01)
    assert eep_to_rft("f6-02-01") == (0xF6, 0x02, 0x01)
    with pytest.raises(ValueError):
        eep_to_rft("nonsense")


def test_load_devices_yaml(tmp_path):
    p = tmp_path / "devices.yaml"
    p.write_text(
        textwrap.dedent("""
        devices:
          - name: Wetter
            address: 0x059ED79A
            eep: A5-13-01
          - name: Rollo
            address: 0xFF94CE9C
            model: eltako/FSB14
            sender: 0xFFAE7C81
            shut_time: 62
    """)
    )
    sensors = {s["name"]: s for s in load_devices_yaml(str(p), "enocean2mqtt/")}
    w = sensors["enocean2mqtt/Wetter"]
    assert (w["rorg"], w["func"], w["type"]) == (0xA5, 0x13, 0x01)
    assert w["address"] == 0x059ED79A
    r = sensors["enocean2mqtt/Rollo"]
    assert r["model"] == "eltako/FSB14" and r["shut_time"] == 62


def test_validation_requires_exactly_one_of_eep_or_model():
    with pytest.raises(ValueError, match="exactly one of 'eep' or 'model'"):
        device_to_sensor({"name": "x", "address": 1}, "e/")  # neither
    with pytest.raises(ValueError, match="exactly one of 'eep' or 'model'"):
        device_to_sensor(
            {"name": "x", "address": 1, "eep": "A5-13-01", "model": "eltako/FSR14"}, "e/"
        )


def test_validation_ignore_only_entry_needs_no_eep():
    # TX echo-suppression entries carry only address + ignore.
    s = device_to_sensor({"name": "echo", "address": 0xFFAE7C81, "ignore": True}, "e/")
    assert s["ignore"] and s.address == 0xFFAE7C81  # ignore coerced to int 1


def test_validation_missing_name_or_address_raises():
    with pytest.raises(ValueError, match="needs 'name' and 'address'"):
        device_to_sensor({"name": "x"}, "e/")


def test_validation_unknown_key_warns_but_loads(caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="enocean2mqtt.devices"):
        s = device_to_sensor({"name": "x", "address": 1, "eep": "A5-13-01", "typoo": 5}, "e/")
    assert "typoo" in caplog.text
    assert s.rorg == 0xA5  # still loaded


def test_duplicate_addresses():
    sensors = [
        {"name": "A", "address": 0x059ED79A, "rorg": 0xA5},
        {"name": "B", "address": 0x059ED79A, "rorg": 0xA5},  # same addr+rorg -> shadows A
        {"name": "C", "address": 0x059ED79A, "rorg": 0xF6},  # same addr, different rorg -> ok
    ]
    assert duplicate_addresses(sensors) == {(0x059ED79A, 0xA5): ["A", "B"]}


def test_address_and_sender_out_of_range_raise():
    with pytest.raises(ValueError, match="out of range"):
        device_to_sensor({"name": "x", "address": 0x1FFFFFFFF, "eep": "A5-13-01"}, "e/")
    with pytest.raises(ValueError, match="out of range"):
        device_to_sensor({"name": "x", "address": 1, "model": "eltako/fsr14", "sender": -1}, "e/")
