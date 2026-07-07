"""Learn-mode auto-provisioning: appending to devices.yaml preserves comments/formatting."""

import os
import tempfile

from enocean2mqtt.devices import append_device_to_yaml, load_devices_yaml

_ENTRY = {"name": "auto_0194E3B9", "address": "0x0194E3B9", "eep": "D2-01-01"}


def _write(text):
    path = os.path.join(tempfile.mkdtemp(), "devices.yaml")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def test_append_preserves_comments_and_formatting():
    path = _write(
        "# my devices file\n"
        "devices:\n"
        "  - name: kitchen  # the good one\n"
        "    address: '0x05000001'\n"
        "    eep: A5-38-08\n"
    )
    assert append_device_to_yaml(path, dict(_ENTRY)) is True

    text = open(path, encoding="utf-8").read()
    assert "# my devices file" in text  # top-of-file comment preserved
    assert "# the good one" in text  # inline comment preserved
    assert "auto_0194E3B9" in text  # new device appended

    sensors = load_devices_yaml(path, "enocean/")
    assert len(sensors) == 2
    assert any(s.address == 0x0194E3B9 for s in sensors)


def test_append_is_idempotent_by_address():
    path = _write("devices:\n  - name: a\n    address: '0x0194E3B9'\n    eep: D2-01-01\n")
    assert append_device_to_yaml(path, dict(_ENTRY)) is False  # address already present
    assert len(load_devices_yaml(path, "enocean/")) == 1


def test_append_creates_file_when_missing():
    path = os.path.join(tempfile.mkdtemp(), "devices.yaml")
    assert append_device_to_yaml(path, dict(_ENTRY)) is True
    sensors = load_devices_yaml(path, "enocean/")
    assert len(sensors) == 1
    assert sensors[0].address == 0x0194E3B9


def test_append_into_empty_devices_list():
    path = _write("devices:\n")
    assert append_device_to_yaml(path, dict(_ENTRY)) is True
    assert len(load_devices_yaml(path, "enocean/")) == 1
