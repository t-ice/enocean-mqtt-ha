"""Device-list loading.

The device list is a ``devices.yaml`` (this module): a device needs only a ``name`` + ``address``
plus either an ``eep`` string (e.g. ``A5-13-01``) or a ``model`` (e.g. ``eltako/FSB14``). The
``rorg``/``func``/``type`` are derived from the EEP string here. The loader produces the in-memory
sensor dicts the rest of the daemon consumes.
"""

from __future__ import annotations

import logging
import os
import re

import yaml

from enocean2mqtt.domain.sensor import Sensor

logger = logging.getLogger("enocean2mqtt.devices")

_EEP_RE = re.compile(r"^\s*([0-9A-Fa-f]{2})-([0-9A-Fa-f]{2})-([0-9A-Fa-f]{2})\s*$")

# Keys kept as strings (everything else is coerced to int).
STRING_KEYS = {
    "command",
    "channel",
    "publish_json",
    "publish_rssi",
    "publish_date",
    "persistent",
    "default_data",
    "model",
    "key",
    "security",
    "key_snd",
}

# Keys a devices.yaml entry may carry; anything else is flagged (typo guard).
KNOWN_KEYS = {
    "name",
    "address",
    "eep",
    "model",
    "sender",
    "shut_time",
    "ignore",
    "command",
    "channel",
    "default_data",
    "direction",
    "answer",
    "log_learn",
    "virtual",
    "publish_json",
    "publish_rssi",
    "publish_date",
    "persistent",
    "security",
    "key",
    "rlc",
    "slf",
    "key_snd",
    "rlc_snd",
}


def eep_to_rft(eep: str) -> tuple[int, int, int]:
    """'A5-13-01' -> (0xA5, 0x13, 0x01)."""
    m = _EEP_RE.match(eep)
    if not m:
        raise ValueError(f"Invalid EEP string: {eep!r} (expected RORG-FUNC-TYPE, e.g. A5-13-01)")
    return int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16)


def _coerce(key: str, value):
    if key in STRING_KEYS:
        return str(value)
    if isinstance(value, str):
        return int(value, 0)  # accepts "0xFF94CE9C" and decimal
    return int(value)


def _validate(device: dict) -> None:
    """Reject structurally invalid entries; warn on soft problems (unknown keys, unknown EEP)."""
    name = device.get("name", "?")
    if "name" not in device or "address" not in device:
        raise ValueError(f"device entry needs 'name' and 'address': {device!r}")

    unknown = set(device) - KNOWN_KEYS
    if unknown:
        logger.warning("device %r: ignoring unknown key(s): %s", name, ", ".join(sorted(unknown)))

    # Ignore-only entries (e.g. TX echo suppression, matched by address then skipped) carry no EEP.
    if device.get("ignore"):
        return

    if ("eep" in device) == ("model" in device):
        raise ValueError(f"device {name!r} needs exactly one of 'eep' or 'model'")
    if "model" in device and "sender" not in device:
        logger.warning("device %r is a model actuator but has no 'sender' — it cannot send", name)
    if "eep" in device:
        from enocean2mqtt.protocol.profiles import PROFILES

        if eep_to_rft(str(device["eep"])) not in PROFILES:
            logger.warning("device %r: EEP %s is not known to the engine", name, device["eep"])

    # Secure telegrams (P5): a security-enabled device needs a 16-byte (32 hex char) AES key.
    if device.get("security"):
        key = str(device.get("key", "")).strip()
        if len(key) != 32 or not all(c in "0123456789abcdefABCDEF" for c in key):
            raise ValueError(f"device {name!r}: 'security' needs a 32-hex-char 'key' (got {key!r})")


def device_to_sensor(device: dict, mqtt_prefix: str) -> Sensor:
    """Validate + convert one devices.yaml entry into the daemon's :class:`Sensor`."""
    _validate(device)

    sensor: dict = {"name": mqtt_prefix + str(device["name"])}
    for key, value in device.items():
        if key == "name":
            continue
        if key == "eep":
            rorg, func, type_ = eep_to_rft(str(value))
            sensor["rorg"], sensor["func"], sensor["type"] = rorg, func, type_
            continue
        coerced = _coerce(key, value)
        if key in ("address", "sender") and not 0 <= coerced <= 0xFFFFFFFF:
            raise ValueError(
                f"device {device['name']!r}: {key} {value!r} out of range (0..0xFFFFFFFF)"
            )
        sensor[key] = coerced
    return Sensor.from_dict(sensor)


def duplicate_senders(sensors: list[dict]) -> dict[int, list[str]]:
    """Return {sender: [device names]} for any sender used by more than one device.

    Two actuators sharing a ``sender`` (base_id + offset) will both act on the same command — a
    hard-to-debug field failure. The daemon logs these at startup so they can be fixed.
    """
    by_sender: dict[int, list[str]] = {}
    for s in sensors:
        sender = s.get("sender")
        if sender is not None:
            by_sender.setdefault(sender, []).append(s.get("name", "?"))
    return {sender: names for sender, names in by_sender.items() if len(names) > 1}


def duplicate_addresses(sensors: list[dict]) -> dict[tuple[int, int | None], list[str]]:
    """Return {(address, rorg): [names]} for any address+RORG claimed by more than one device.

    The daemon matches an incoming telegram to the FIRST sensor with that (address, RORG), so a
    duplicate silently shadows the later device. Warned at startup (not fatal — the same address
    under different RORGs is legitimate).
    """
    by_key: dict[tuple[int, int | None], list[str]] = {}
    for s in sensors:
        address = s.get("address")
        if address is not None:
            by_key.setdefault((address, s.get("rorg")), []).append(s.get("name", "?"))
    return {k: names for k, names in by_key.items() if len(names) > 1}


def load_devices_yaml(path: str, mqtt_prefix: str = "enocean/") -> list[Sensor]:
    """Load a devices.yaml file into a list of :class:`Sensor` objects."""
    with open(path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh) or {}
    devices = doc.get("devices", doc if isinstance(doc, list) else [])
    return [device_to_sensor(d, mqtt_prefix) for d in devices]


# --- Learn-mode auto-provisioning ---
# Devices taught in via the HA LEARN button are appended straight to the user's own devices.yaml,
# so they load normally on the next start. ruamel.yaml (round-trip) is used for the write so the
# file's existing comments and formatting are preserved (pyyaml cannot round-trip comments).


def append_device_to_yaml(devices_yaml_path: str, entry: dict) -> bool:
    """Append a device to devices.yaml, preserving comments/formatting. Idempotent by address.

    Returns True if newly added, False if the address is already present. Creates the file (and the
    ``devices:`` list) if missing.
    """
    from ruamel.yaml import YAML

    ryaml = YAML()  # round-trip mode: keeps comments + formatting
    ryaml.preserve_quotes = True
    ryaml.indent(mapping=2, sequence=2, offset=0)

    doc = None
    if os.path.isfile(devices_yaml_path):
        with open(devices_yaml_path, encoding="utf-8") as fh:
            doc = ryaml.load(fh)
    if doc is None:
        doc = {}
    if not doc.get("devices"):
        doc["devices"] = []
    devices = doc["devices"]

    addr = int(str(entry["address"]), 0)
    for d in devices:
        try:
            if int(str(d.get("address", "")), 0) == addr:
                return False  # already configured — don't duplicate
        except (TypeError, ValueError):
            continue

    devices.append(entry)
    os.makedirs(os.path.dirname(devices_yaml_path) or ".", exist_ok=True)
    tmp = devices_yaml_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        ryaml.dump(doc, fh)
    os.replace(tmp, devices_yaml_path)  # atomic
    return True
