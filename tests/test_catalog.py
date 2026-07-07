"""Catalog consistency: well-formed entries, valid EEPs, and 'verified' devices really mapped."""

from pathlib import Path

import pytest
import yaml

from enocean2mqtt.devices import eep_to_rft
from enocean2mqtt.homeassistant.mapping import MAPPING

_CATALOG_FILE = Path(__file__).resolve().parents[1] / "catalog" / "eltako_devices.yaml"
CATALOG = yaml.safe_load(_CATALOG_FILE.read_text(encoding="utf-8"))["devices"]
VALID_TIERS = {"verified", "manual", "generic"}


def is_mapped(device: dict, mapping: dict) -> bool:
    """True if the device is actually covered by the code-defined MAPPING."""
    if "model_key" in device:
        return device["model_key"] in mapping.get("eltako", {})
    if "eep" in device:
        r, f, t = (int(x, 16) for x in device["eep"].split("-"))
        return t in mapping.get(r, {}).get(f, {})
    return False


def test_catalog_not_empty():
    assert CATALOG


@pytest.mark.parametrize("slug", list(CATALOG))
def test_entry_well_formed(slug):
    dev = CATALOG[slug]
    assert dev.get("manufacturer"), f"{slug}: manufacturer required"
    assert dev.get("category"), f"{slug}: category required"
    entity_types = dev.get("entity_types")
    assert isinstance(entity_types, list) and entity_types, f"{slug}: entity_types required"
    assert dev.get("verification") in VALID_TIERS, f"{slug}: bad verification tier"
    assert ("model_key" in dev) or ("eep" in dev), f"{slug}: needs model_key or eep"


@pytest.mark.parametrize("slug", list(CATALOG))
def test_eep_strings_valid(slug):
    dev = CATALOG[slug]
    for field in ("eep", "command_eep"):
        if field in dev:
            eep_to_rft(dev[field])  # raises on malformed
    status = dev.get("status_eep", [])
    for eep in status if isinstance(status, list) else [status]:
        eep_to_rft(eep)


@pytest.mark.parametrize("slug", [s for s, d in CATALOG.items() if d["verification"] == "verified"])
def test_verified_devices_are_actually_mapped(slug):
    """A device can only be 'verified' if the code-defined MAPPING actually covers it."""
    assert is_mapped(CATALOG[slug], MAPPING), (
        f"{slug} is marked 'verified' but is not present in the code-defined MAPPING"
    )
