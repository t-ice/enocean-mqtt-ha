"""'sender: auto' — one-time sender assignment, write-back to devices.yaml, and the range check.

Built on the real loader + bridge with a temp devices.yaml, so the whole chain is exercised:
YAML -> Sensor -> (model expansion) -> assignment -> file write-back -> discovery / sending.
"""

import asyncio
import logging
import textwrap
from unittest import mock

import pytest

from enocean2mqtt.application import daemon as daemon_module
from enocean2mqtt.devices import load_devices_yaml, set_auto_sender_in_yaml
from enocean2mqtt.homeassistant import ha_bridge as ha_bridge_module
from enocean2mqtt.homeassistant.ha_bridge import HomeAssistantBridge

BASE = 0xFFAE7C80
BASE_BYTES = [0xFF, 0xAE, 0x7C, 0x80]
PREFIX = "enocean2mqtt/"

AUTO_YAML = """
    # my devices
    devices:
      - name: Licht_Flur            # fixed, taught long ago
        address: 0x05000001
        model: eltako/FSR14
        sender: 0xFFAE7C85
      - name: Rollo_Bad
        address: 0x05000002
        model: eltako/FSB14
        sender: auto                # let the bridge pick
        shut_time: 30
      - name: Licht_Kueche
        address: 0x05000003
        model: eltako/FSR14
        sender: AUTO
      - name: Wetter
        address: 0x05000004
        eep: A5-13-01
"""


def make_bridge(tmp_path, yaml_text=AUTO_YAML, base=BASE_BYTES):
    """A bridge loaded from a temp devices.yaml; ``base`` is the Base ID the stick reported."""
    device_file = tmp_path / "devices.yaml"
    if not device_file.exists():
        device_file.write_text(textwrap.dedent(yaml_text))
    conf = {
        "mqtt_host": "x",
        "mqtt_port": "1883",
        "mqtt_prefix": PREFIX,
        "mqtt_discovery_prefix": "homeassistant/",
        "enocean_port": "socket://127.0.0.1:3000",
        "db_file": str(tmp_path / "db.sqlite"),
        "device_file": str(device_file),
    }
    bridge = HomeAssistantBridge(conf, load_devices_yaml(str(device_file), PREFIX))
    bridge._daemon.publish = mock.AsyncMock()
    if base is not None:
        bridge._daemon.enocean_sender = list(base)
        bridge._daemon.base_id_ready.set()
    return bridge, device_file


def senders_by_name(bridge):
    """{sensor name: sender} over the (expanded) sensor list."""
    return {s.name: s.sender for s in bridge.sensors}


def published_topics(bridge):
    return [call.args[0] for call in bridge._daemon.publish.await_args_list]


# --- loader ---------------------------------------------------------------------------------------


def test_loader_marks_auto_sender_instead_of_failing(tmp_path):
    p = tmp_path / "devices.yaml"
    p.write_text(textwrap.dedent(AUTO_YAML))
    sensors = {s.name: s for s in load_devices_yaml(str(p), PREFIX)}
    rollo = sensors[PREFIX + "Rollo_Bad"]
    assert rollo.sender is None and rollo.sender_auto == "Rollo_Bad"
    assert sensors[PREFIX + "Licht_Kueche"].sender_auto == "Licht_Kueche"  # case-insensitive
    fixed = sensors[PREFIX + "Licht_Flur"]
    assert fixed.sender == 0xFFAE7C85 and fixed.sender_auto is None
    assert sensors[PREFIX + "Wetter"].sender_auto is None  # no sender key -> unchanged behaviour


def test_loader_still_rejects_other_text_as_sender(tmp_path):
    p = tmp_path / "devices.yaml"
    p.write_text(
        "devices:\n  - {name: X, address: 0x05000001, model: eltako/FSR14, sender: next}\n"
    )
    with pytest.raises(ValueError):
        load_devices_yaml(str(p), PREFIX)


# --- assignment -----------------------------------------------------------------------------------


async def test_auto_devices_get_distinct_senders_above_the_highest_in_file_order(tmp_path):
    bridge, _ = make_bridge(tmp_path)
    await bridge.before_connect()
    senders = senders_by_name(bridge)
    # Highest configured offset is 5 -> the two auto devices get 6 and 7, in file order.
    assert senders[PREFIX + "Rollo_Bad/a5"] == BASE + 6
    assert senders[PREFIX + "Licht_Kueche/a5"] == BASE + 7
    assert senders[PREFIX + "Licht_Flur/a5"] == BASE + 5  # fixed sender untouched
    assert senders[PREFIX + "Wetter"] is None  # senderless device stays senderless
    assert bridge._pending_auto_sensors() == []


async def test_all_sensors_expanded_from_one_entry_share_the_assigned_sender(tmp_path):
    bridge, _ = make_bridge(tmp_path)
    await bridge.before_connect()
    rollo = [s for s in bridge.sensors if s.name.startswith(PREFIX + "Rollo_Bad/")]
    assert len(rollo) > 1, "FSB14 is expected to expand into several per-RORG sensors"
    assert {s.sender for s in rollo} == {BASE + 6}
    assert all(s.sender_auto is None for s in rollo)


async def test_assigned_sender_is_written_back_and_comments_survive(tmp_path):
    bridge, device_file = make_bridge(tmp_path)
    await bridge.before_connect()
    text = device_file.read_text()
    assert "sender: 0xFFAE7C86" in text and "sender: 0xFFAE7C87" in text
    assert "auto" not in text.lower().replace("# let the bridge pick", "")
    for kept in ("# my devices", "# fixed, taught long ago", "# let the bridge pick"):
        assert kept in text
    assert "sender: 0xFFAE7C85" in text  # the hand-written one keeps its spelling
    assert not (tmp_path / "devices.yaml.tmp").exists()  # atomic write left nothing behind
    # ...and the written file loads as plain fixed senders.
    reloaded = {s.name: s for s in load_devices_yaml(str(device_file), PREFIX)}
    assert reloaded[PREFIX + "Rollo_Bad"].sender == BASE + 6
    assert reloaded[PREFIX + "Rollo_Bad"].sender_auto is None


async def test_second_start_keeps_the_addresses_and_assigns_nothing_new(tmp_path):
    bridge, device_file = make_bridge(tmp_path)
    await bridge.before_connect()
    first = device_file.read_text()

    again, _ = make_bridge(tmp_path)  # same file + same store = a restart
    await again.before_connect()
    assert device_file.read_text() == first
    assert senders_by_name(again)[PREFIX + "Rollo_Bad/a5"] == BASE + 6
    assert again._sender_announcements == []


async def test_before_connect_twice_is_idempotent(tmp_path):
    bridge, device_file = make_bridge(tmp_path)
    await bridge.before_connect()
    first = device_file.read_text()
    await bridge.before_connect()  # e.g. a broker reconnect
    assert device_file.read_text() == first


async def test_address_of_a_removed_device_is_never_handed_out_again(tmp_path):
    bridge, device_file = make_bridge(tmp_path)
    await bridge.before_connect()  # Rollo_Bad=+6, Licht_Kueche=+7

    # The user deletes Licht_Kueche (highest address) and adds a new auto device.
    device_file.write_text(
        textwrap.dedent("""
        devices:
          - name: Rollo_Bad
            address: 0x05000002
            model: eltako/FSB14
            sender: 0xFFAE7C86
          - name: Neu
            address: 0x05000009
            model: eltako/FSR14
            sender: auto
        """)
    )
    again, _ = make_bridge(tmp_path)
    await again.before_connect()
    # +7 still belongs to the removed actuator -> the new device gets +8, not +7.
    assert senders_by_name(again)[PREFIX + "Neu/a5"] == BASE + 8


async def test_high_water_is_kept_per_base_id(tmp_path):
    bridge, _ = make_bridge(tmp_path)
    await bridge.before_connect()
    assert bridge._devmgr.get_sender_high_water(BASE) == 7
    assert bridge._devmgr.get_sender_high_water(0xFF112200) == 0  # another stick starts fresh


async def test_pool_exhausted_leaves_the_device_inactive(tmp_path, caplog):
    yaml_text = """
        devices:
          - name: Voll
            address: 0x05000001
            model: eltako/FSR14
            sender: 0xFFAE7CFF
          - name: Neu
            address: 0x05000002
            model: eltako/FSR14
            sender: auto
    """
    bridge, device_file = make_bridge(tmp_path, yaml_text)
    with caplog.at_level(logging.ERROR):
        await bridge.before_connect()
    assert "No free sender left for Neu" in caplog.text
    assert senders_by_name(bridge)[PREFIX + "Neu/a5"] is None
    assert "sender: auto" in device_file.read_text()


async def test_unwritable_devices_yaml_means_no_assignment(tmp_path, caplog, monkeypatch):
    bridge, device_file = make_bridge(tmp_path)
    before = device_file.read_text()
    monkeypatch.setattr(
        ha_bridge_module, "set_auto_sender_in_yaml", mock.Mock(side_effect=PermissionError("ro"))
    )
    with caplog.at_level(logging.ERROR):
        await bridge.before_connect()
    assert "Cannot assign a sender to Rollo_Bad" in caplog.text
    assert senders_by_name(bridge)[PREFIX + "Rollo_Bad/a5"] is None
    assert device_file.read_text() == before
    # Nothing was consumed: once the file is writable the device gets the very same address.
    monkeypatch.undo()
    await bridge.before_connect()
    assert senders_by_name(bridge)[PREFIX + "Rollo_Bad/a5"] == BASE + 6


async def test_no_device_file_means_no_assignment(tmp_path, caplog):
    bridge, _ = make_bridge(tmp_path)
    bridge._daemon.conf.get = mock.Mock(return_value=None)
    with caplog.at_level(logging.ERROR):
        await bridge.before_connect()
    assert "no devices.yaml path is known" in caplog.text
    assert bridge._pending_auto_sensors() != []


# --- write-back helper ----------------------------------------------------------------------------


def test_write_back_never_overwrites_a_sender_the_user_fixed_meanwhile(tmp_path):
    p = tmp_path / "devices.yaml"
    p.write_text(
        "devices:\n"
        "  - {name: A, address: 0x05000001, model: eltako/FSR14, sender: 0xFFAE7C90}\n"
        "  - {name: B, address: 0x05000002, model: eltako/FSR14, sender: auto}\n"
    )
    before = p.read_text()
    assert set_auto_sender_in_yaml(str(p), "A", 0x05000001, BASE + 1) is False  # not 'auto'
    assert set_auto_sender_in_yaml(str(p), "B", 0x05000099, BASE + 1) is False  # other address
    assert set_auto_sender_in_yaml(str(p), "C", 0x05000002, BASE + 1) is False  # unknown name
    assert p.read_text() == before
    assert set_auto_sender_in_yaml(str(p), "B", 0x05000002, BASE + 1) is True
    assert load_devices_yaml(str(p), PREFIX)[1].sender == BASE + 1


# --- discovery + sending --------------------------------------------------------------------------


async def test_discovery_uses_the_assigned_sender_never_none(tmp_path):
    bridge, _ = make_bridge(tmp_path)
    await bridge.before_connect()
    await bridge.after_connect()
    uids = bridge._devmgr.db_list_from_fields("uid")
    assert any(uid.endswith("05000002_FFAE7C86") for uid in uids), uids
    assert not any("05000002_NONE" in uid for uid in uids), uids


async def test_assignment_is_announced_over_mqtt(tmp_path):
    bridge, _ = make_bridge(tmp_path)
    await bridge.before_connect()
    await bridge.after_connect()
    calls = [
        c
        for c in bridge._daemon.publish.await_args_list
        if c.args[0] == PREFIX + "bridge/last_assigned_sender"
    ]
    assert [c.args[1] for c in calls] == [
        '{"name": "Rollo_Bad", "sender": "0xFFAE7C86"}',
        '{"name": "Licht_Kueche", "sender": "0xFFAE7C87"}',
    ]
    assert all(c.kwargs == {"retain": True} for c in calls)


async def test_command_is_transmitted_from_the_assigned_sender(tmp_path):
    """End to end in-process: YAML 'auto' -> assignment -> the encoder gets the assigned address."""
    bridge, _ = make_bridge(tmp_path)
    await bridge.before_connect()
    rollo = next(s for s in bridge.sensors if s.name == PREFIX + "Rollo_Bad/a5")
    sent = []
    bridge._daemon._transport.send = mock.AsyncMock(side_effect=sent.append)
    rollo["data"] = {"DB3": 0, "DB2": 30, "DB1": 1, "DB0": 8}
    await bridge._daemon._send_packet(rollo, [0xFF, 0xFF, 0xFF, 0xFF])
    assert len(sent) == 1
    assert sent[0].sender == [0xFF, 0xAE, 0x7C, 0x86]


# --- no Base ID -----------------------------------------------------------------------------------


@pytest.fixture
def fast_base_id_timeout(monkeypatch):
    monkeypatch.setattr(ha_bridge_module, "_BASE_ID_TIMEOUT", 0.01)
    monkeypatch.setattr(daemon_module, "_BASE_ID_TIMEOUT", 0.01)


async def test_without_base_id_auto_devices_are_not_assigned_discovered_or_sent(
    tmp_path, fast_base_id_timeout
):
    bridge, device_file = make_bridge(tmp_path, base=None)
    before = device_file.read_text()
    await bridge.before_connect()
    await bridge.after_connect()
    try:
        assert device_file.read_text() == before
        uids = bridge._devmgr.db_list_from_fields("uid")
        assert not any("05000002" in uid for uid in uids), uids  # no "…_NONE" entities
        assert any("05000001" in uid for uid in uids)  # the fixed device is announced as usual

        # Even with a Base ID fallback available, an unassigned auto device must not transmit.
        rollo = next(s for s in bridge.sensors if s.name == PREFIX + "Rollo_Bad/a5")
        bridge._daemon._encoder.send = mock.AsyncMock()
        bridge._daemon.enocean_sender = list(BASE_BYTES)
        await bridge._daemon._send_packet(rollo, [0xFF, 0xFF, 0xFF, 0xFF])
        bridge._daemon._encoder.send.assert_not_awaited()
    finally:
        bridge._late_sender_task.cancel()


async def test_late_base_id_assigns_and_discovers_afterwards(tmp_path, fast_base_id_timeout):
    bridge, device_file = make_bridge(tmp_path, base=None)
    await bridge.before_connect()
    await bridge.after_connect()  # discovery ran without the auto devices
    assert bridge._late_sender_task is not None

    bridge._daemon.enocean_sender = list(BASE_BYTES)  # the stick finally answers
    bridge._daemon.base_id_ready.set()
    await asyncio.wait_for(bridge._late_sender_task, timeout=2)

    assert senders_by_name(bridge)[PREFIX + "Rollo_Bad/a5"] == BASE + 6
    assert "sender: 0xFFAE7C86" in device_file.read_text()
    uids = bridge._devmgr.db_list_from_fields("uid")
    assert any(uid.endswith("05000002_FFAE7C86") for uid in uids), uids
    assert PREFIX + "bridge/last_assigned_sender" in published_topics(bridge)


async def test_late_base_id_before_first_connect_is_discovered_by_after_connect(
    tmp_path, fast_base_id_timeout
):
    bridge, _ = make_bridge(tmp_path, base=None)
    await bridge.before_connect()
    bridge._daemon.enocean_sender = list(BASE_BYTES)  # answers before the broker connects
    bridge._daemon.base_id_ready.set()
    await asyncio.wait_for(bridge._late_sender_task, timeout=2)
    assert PREFIX + "bridge/last_assigned_sender" not in published_topics(bridge)  # not connected

    await bridge.after_connect()
    uids = bridge._devmgr.db_list_from_fields("uid")
    assert any(uid.endswith("05000002_FFAE7C86") for uid in uids), uids
    assert PREFIX + "bridge/last_assigned_sender" in published_topics(bridge)


async def test_base_id_seen_on_a_reconnect_still_gets_the_device_discovered(
    tmp_path, fast_base_id_timeout
):
    bridge, _ = make_bridge(tmp_path, base=None)
    await bridge.before_connect()
    await bridge.after_connect()  # first connect: discovery ran without the auto devices
    bridge._late_sender_task.cancel()  # the waiting task never got to run (worst case)

    bridge._daemon.enocean_sender = list(BASE_BYTES)
    bridge._daemon.base_id_ready.set()
    await bridge.before_connect()  # broker reconnect
    await bridge.after_connect()
    uids = bridge._devmgr.db_list_from_fields("uid")
    assert any(uid.endswith("05000002_FFAE7C86") for uid in uids), uids
    assert PREFIX + "bridge/last_assigned_sender" in published_topics(bridge)


async def test_late_assignment_error_is_logged_not_swallowed(
    tmp_path, fast_base_id_timeout, caplog, monkeypatch
):
    bridge, _ = make_bridge(tmp_path, base=None)
    await bridge.before_connect()
    monkeypatch.setattr(bridge, "_resolve_senders", mock.Mock(side_effect=RuntimeError("boom")))
    bridge._daemon.base_id_ready.set()
    with caplog.at_level(logging.ERROR):
        await asyncio.wait_for(bridge._late_sender_task, timeout=2)
    assert "Assigning the 'sender: auto' devices failed" in caplog.text


async def test_secure_teach_in_is_not_sent_for_an_unassigned_auto_device(tmp_path):
    bridge, _ = make_bridge(tmp_path)  # Base ID known, but before_connect has not run yet
    rollo = next(s for s in bridge.sensors if s.name == PREFIX + "Rollo_Bad/a5")
    rollo["key"] = "00112233445566778899AABBCCDDEEFF"
    bridge._daemon._transport.send = mock.AsyncMock()
    await bridge._daemon.send_secure_teach_in(rollo)
    bridge._daemon._transport.send.assert_not_awaited()


# --- range check ----------------------------------------------------------------------------------


async def test_out_of_range_sender_is_warned_once_per_device(tmp_path, caplog):
    yaml_text = """
        devices:
          - name: Alt
            address: 0x05000001
            model: eltako/FSB14
            sender: 0xFF112233
          - name: Gut
            address: 0x05000002
            model: eltako/FSR14
            sender: 0xFFAE7CFF
          - name: Wetter
            address: 0x05000004
            eep: A5-13-01
    """
    bridge, _ = make_bridge(tmp_path, yaml_text)
    with caplog.at_level(logging.WARNING):
        await bridge.before_connect()
        await bridge.before_connect()  # a reconnect must not repeat the warning
    warnings = [r.getMessage() for r in caplog.records if "outside this transceiver" in r.message]
    assert len(warnings) == 1, warnings  # once, although FSB14 expands into several sensors
    assert "0xFF112233" in warnings[0] and "Alt" in warnings[0]
    assert "0xFFAE7C80-0xFFAE7CFF" in warnings[0]
