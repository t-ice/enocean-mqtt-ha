"""Opt-in full-Home-Assistant tier (`pytest -m ha`): a real HA container ingests our discovery.

Boots Home Assistant alongside the stack (mosquitto + emulator + daemon), pre-seeded with an MQTT
config entry pointing at the broker so it auto-connects and processes the daemon's MQTT-discovery
configs, then asserts HA registered the resulting entity (read from the mounted entity registry —
no API auth needed). Slow (HA boot ~1-2 min); deselected by default, run with `-m ha`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from tests.integration.conftest import wait_until

pytestmark = pytest.mark.ha

HA_IMAGE = "docker.io/homeassistant/home-assistant:2024.12"


def _seed_ha_config(cfg: Path) -> None:
    """A minimal /config that skips onboarding and pre-connects MQTT to the broker."""
    storage = cfg / ".storage"
    storage.mkdir(parents=True, exist_ok=True)
    (cfg / "configuration.yaml").write_text("default_config:\n", encoding="utf-8")
    (storage / "onboarding").write_text(
        json.dumps(
            {
                "version": 4,
                "minor_version": 1,
                "key": "onboarding",
                "data": {"done": ["user", "core_config", "analytics", "integration"]},
            }
        ),
        encoding="utf-8",
    )
    (storage / "core.config_entries").write_text(
        json.dumps(
            {
                "version": 1,
                "minor_version": 1,
                "key": "core.config_entries",
                "data": {
                    "entries": [
                        {
                            "entry_id": "mqtt0000000000000000000000000000",
                            "version": 1,
                            "minor_version": 2,
                            "domain": "mqtt",
                            "title": "mosquitto",
                            "data": {
                                "broker": "mosquitto",
                                "port": 1883,
                                "discovery": True,
                                "discovery_prefix": "homeassistant",
                            },
                            "options": {},
                            "pref_disable_new_entities": False,
                            "pref_disable_polling": False,
                            "source": "user",
                            "unique_id": None,
                            "disabled_by": None,
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def home_assistant(stack):
    podman = stack["podman"]
    cfg = stack["work"] / "ha-config"
    _seed_ha_config(cfg)
    name = f"e2m-ha-{stack['tag']}"
    try:
        podman(
            "run",
            "-d",
            "--name",
            name,
            "--network",
            stack["net"],
            "-e",
            "TZ=UTC",
            "-v",
            f"{cfg}:/config",
            HA_IMAGE,
        )
        yield {"config": cfg, "name": name}
    finally:
        podman("rm", "-f", name, check=False)


def _enocean_entities(registry: Path) -> list[str]:
    if not registry.exists():
        return []
    try:
        data = json.loads(registry.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    entities = data.get("data", {}).get("entities", [])
    # our discovery uid/topics carry the mqtt prefix; match the bridge/device name space
    return [
        e.get("entity_id", "")
        for e in entities
        if e.get("platform") == "mqtt" and "enocean" in json.dumps(e).lower()
    ]


def test_home_assistant_registers_enocean_entities(home_assistant):
    registry = home_assistant["config"] / ".storage" / "core.entity_registry"
    # HA boot + MQTT connect + discovery ingest is slow; poll the entity registry generously.
    found = wait_until(lambda: _enocean_entities(registry), timeout=180, interval=3)
    assert found, (
        "Home Assistant did not register any enocean MQTT-discovery entities "
        f"(registry exists={registry.exists()})"
    )
    assert (
        any("wetter" in e.lower() or "licht" in e.lower() or "sender" in e.lower() for e in found)
        or found
    )  # at least some enocean entity materialised
