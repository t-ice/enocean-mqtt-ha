"""Podman-driven fixtures for the container integration tier (`pytest -m integration`).

Stands up the real stack: a mosquitto broker, a ser2net/ESP3 **emulator** (the fake Pi + stick),
and the **actual add-on image** running the daemon against both. Everything is torn down after.

macOS/podman notes handled here: podman may not be on the tool PATH (we resolve the binary), and
only ``$HOME`` is mounted into the podman VM, so the per-test workspace lives under the repo (not
``/var/folders``) to be mountable.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "tests" / "fixtures" / "telegrams"
IMAGE = "e2m-itest:latest"


def _find_podman() -> str | None:
    for cand in (
        "podman",
        "/opt/podman/bin/podman",
        "/opt/homebrew/bin/podman",
        "/usr/local/bin/podman",
    ):
        path = shutil.which(cand) or (cand if os.path.exists(cand) else None)
        if path:
            return path
    return None


PODMAN = _find_podman()
pytestmark = pytest.mark.integration


def podman(*args: str, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PODMAN, *args],
        check=check,
        text=True,
        capture_output=capture,
        timeout=300,
    )


@pytest.fixture(scope="session", autouse=True)
def _require_podman():
    if PODMAN is None:
        pytest.skip("podman not available")
    try:
        podman("info")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pytest.skip("podman machine not running")


@pytest.fixture(scope="session")
def addon_image(_require_podman):
    """Build the integration image once — the same daemon package as the add-on, plain base."""
    podman(
        "build",
        "-f",
        str(REPO / "tests" / "integration" / "Dockerfile"),
        "-t",
        IMAGE,
        str(REPO),
        capture=False,
    )
    return IMAGE


@pytest.fixture
def stack(addon_image, tmp_path_factory):
    """A fresh network + mosquitto + emulator + daemon; yields handles for assertions."""
    tag = uuid.uuid4().hex[:8]
    net = f"e2m-net-{tag}"
    names = {n: f"e2m-{n}-{tag}" for n in ("mosq", "emu", "daemon")}
    # Workspace under the repo so podman (macOS) can bind-mount it.
    work = REPO / "tests" / "integration" / ".tmp" / tag
    work.mkdir(parents=True, exist_ok=True)
    host_mqtt_port = 21883

    def cleanup():
        for n in names.values():
            podman("rm", "-f", n, check=False)
        podman("network", "rm", net, check=False)
        shutil.rmtree(work, ignore_errors=True)

    try:
        podman("network", "create", net)

        # --- mosquitto (anonymous) ---
        (work / "mosquitto.conf").write_text(
            "listener 1883\nallow_anonymous true\n", encoding="utf-8"
        )
        podman(
            "run",
            "-d",
            "--name",
            names["mosq"],
            "--network",
            net,
            "--network-alias",
            "mosquitto",
            "-p",
            f"{host_mqtt_port}:1883",
            "-v",
            f"{work / 'mosquitto.conf'}:/mosquitto/config/mosquitto.conf:ro",
            "docker.io/library/eclipse-mosquitto:2",
        )

        # --- emulator (real image; runs emulator.py; A5-10-03 telegram + base id FFAE7C80) ---
        telegram = sorted(FIXTURES.glob("received_a5_051E70DE_*.json"))[0]
        podman(
            "run",
            "-d",
            "--name",
            names["emu"],
            "--network",
            net,
            "--network-alias",
            "emulator",
            "-e",
            "EMU_PORT=3000",
            "-e",
            "EMU_BASE_ID=FFAE7C80",
            "-e",
            f"EMU_TELEGRAMS=/fixtures/{telegram.name}",
            "-e",
            "EMU_CAPTURE=/capture/sent.hex",
            "-e",
            "EMU_REPLAY_DELAY=2",
            "-v",
            f"{REPO / 'tests' / 'integration' / 'emulator.py'}:/emulator.py:ro",
            "-v",
            f"{FIXTURES}:/fixtures:ro",
            "-v",
            f"{work}:/capture",
            IMAGE,
            "python",
            "/emulator.py",
        )

        # --- daemon config (real image, entrypoint overridden to run the console script) ---
        (work / "e.conf").write_text(
            "[CONFIG]\n"
            "enocean_port          = emulator:3000\n"
            "mqtt_host             = mosquitto\n"
            "mqtt_port             = 1883\n"
            "mqtt_prefix           = enocean2mqtt/\n"
            "mqtt_discovery_prefix = homeassistant/\n"
            "overlay               = HA\n"
            "db_file               = /data/db.sqlite\n",
            encoding="utf-8",
        )
        # 'Wetter' decodes the replayed telegram; 'Sender' is a no-command BS4 profile proving an
        # inbound raw_data command reaches the wire (command profiles need a command, not raw_data).
        (work / "devices.yaml").write_text(
            "devices:\n"
            "  - name: Wetter\n"
            "    address: 0x051E70DE\n"
            "    eep: A5-10-03\n"
            "  - name: Sender\n"
            "    address: 0xFFAE7C90\n"
            "    eep: A5-02-05\n"
            "    sender: 0xFFAE7C90\n",
            encoding="utf-8",
        )
        podman(
            "run",
            "-d",
            "--name",
            names["daemon"],
            "--network",
            net,
            "--entrypoint",
            "enocean2mqtt",
            "-v",
            f"{work}:/data",
            IMAGE,
            "--log-level",
            "debug",
            "--logfile",
            "/data/daemon.log",
            "/data/e.conf",
            "/data/devices.yaml",
        )

        yield {
            "mqtt_port": host_mqtt_port,
            "capture": work / "sent.hex",
            "work": work,
            "net": net,
            "tag": tag,
            "daemon": names["daemon"],
            "emulator": names["emu"],
            "mosquitto": names["mosq"],
            "podman": podman,
        }
    finally:
        cleanup()


class Collector:
    """Subscribes to '#' and records the latest payload per topic; re-subscribes on reconnect so it
    survives a broker restart (retained messages are re-delivered)."""

    def __init__(self, port: int):
        import paho.mqtt.client as mqtt

        self.msgs: dict[str, bytes] = {}
        self._c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="itest")
        self._c.reconnect_delay_set(min_delay=1, max_delay=4)
        self._c.on_connect = lambda c, *_: c.subscribe("#")
        self._c.on_message = lambda _c, _u, m: self.msgs.__setitem__(m.topic, m.payload)
        self._c.connect("127.0.0.1", port, keepalive=15)
        self._c.loop_start()

    def topics_matching(self, needle: str) -> list[str]:
        return [t for t in self.msgs if needle in t]

    def forget(self, needle: str) -> None:
        for t in [t for t in self.msgs if needle in t]:
            del self.msgs[t]

    def publish(self, topic: str, payload: str) -> None:
        self._c.publish(topic, payload)

    def close(self) -> None:
        self._c.loop_stop()
        self._c.disconnect()


def read_capture(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def wait_until(predicate, timeout=30.0, interval=0.5):
    """Poll *predicate* until truthy or timeout; returns the last value."""
    deadline = time.time() + timeout
    val = predicate()
    while not val and time.time() < deadline:
        time.sleep(interval)
        val = predicate()
    return val
