"""Crash safety (review 2026-11): one bad message, one odd telegram or a missing transceiver must
never end the add-on. Each test here failed on 1.0.9 — the daemon exited or dropped its link."""

from __future__ import annotations

import asyncio
import logging
import types
from unittest import mock

import aiomqtt
import pytest

from enocean2mqtt.adapters.transceiver.ser2net_link import Ser2netLink
from enocean2mqtt.application.daemon import EnoceanDaemon
from enocean2mqtt.protocol.constants import PACKET
from enocean2mqtt.protocol.packet import RadioPacket

CONF = {
    "mqtt_host": "x",
    "mqtt_port": "1883",
    "mqtt_prefix": "enocean2mqtt/",
    "enocean_port": "socket://127.0.0.1:3000",
}
DIMMER = {
    "name": "enocean2mqtt/dimmer",
    "address": 0x0500_0001,
    "rorg": 0xA5,
    "func": 0x38,
    "type": 0x08,
    "sender": 0xFFAE7C81,
    "command": "CMD",
}
GOOD_COMMAND = b'{"CMD": 2, "EDIM": 40, "RMP": 0, "EDIMR": 0, "STR": 0, "SW": 1, "send": "clear"}'


def _message(topic: str, payload: bytes):
    return types.SimpleNamespace(topic=types.SimpleNamespace(value=topic), payload=payload)


def _daemon():
    com = EnoceanDaemon(CONF, [dict(DIMMER)])
    com._transport = mock.AsyncMock()  # records every write to the transceiver
    return com


async def _run_with_messages(com, messages):
    """Drive the real run loop with a fake broker delivering *messages*, then shut down."""

    async def deliver():
        for message in messages:
            yield message
        com._shutdown.set()
        await asyncio.sleep(10)  # parked until the shutdown watcher unwinds the TaskGroup

    client = mock.AsyncMock()
    client.messages = deliver()

    class Connection:
        async def __aenter__(self):
            return client

        async def __aexit__(self, *exc):
            return False

    async def idle():
        await asyncio.sleep(10)

    com._make_mqtt_client = Connection
    com._enocean_task = idle
    com._stats_task = idle
    await asyncio.wait_for(com._run_async(), timeout=3)


@pytest.mark.parametrize(
    "bad_payload",
    [
        b'{"EDIM": "abc", "send": "clear"}',  # killed 1.0.9: dict changed size during iteration
        b'{"EDIM": null}',
        b'{"send": 1}',
        b'{"EDIM": [1, 2]}',
    ],
)
async def test_bad_command_is_skipped_and_the_next_one_still_works(bad_payload):
    com = _daemon()
    await _run_with_messages(
        com,
        [
            _message("enocean2mqtt/dimmer/req", bad_payload),
            _message("enocean2mqtt/dimmer/req", GOOD_COMMAND),
        ],
    )
    sent = [c.args[0] for c in com._transport.send.await_args_list]
    assert len(sent) == 1, "the valid command after the bad one must still be transmitted"
    assert sent[0].data[0] == 0xA5


async def test_unexpected_error_in_a_handler_is_counted_not_fatal(caplog):
    com = _daemon()
    com._dispatch_mqtt = mock.AsyncMock(side_effect=[KeyError("bug"), None])
    with caplog.at_level(logging.ERROR):
        await _run_with_messages(com, [_message("a", b"1"), _message("b", b"2")])
    assert com._dispatch_mqtt.await_count == 2  # kept consuming after the error
    assert com._processing_errors == 1
    assert "Error handling MQTT message on a — message ignored" in caplog.text


async def test_broker_error_in_a_handler_still_triggers_the_reconnect():
    com = _daemon()
    com._dispatch_mqtt = mock.AsyncMock(side_effect=aiomqtt.MqttError("broker gone"))
    with pytest.raises(aiomqtt.MqttError):
        await com._handle_mqtt("a", b"1")
    assert com._processing_errors == 0


# --- sending while the transceiver is offline ----------------------------------------------------


async def test_command_while_transceiver_offline_is_dropped_with_a_warning(caplog):
    """The real ser2net link, never connected (= mid-reconnect). 1.0.9 raised RuntimeError here,
    out of the MQTT task — any HA command during a Pi reboot ended the add-on."""
    com = EnoceanDaemon(CONF, [dict(DIMMER)])
    assert isinstance(com._transport, Ser2netLink)
    with caplog.at_level(logging.WARNING):
        await com._handle_mqtt("enocean2mqtt/dimmer/req", GOOD_COMMAND)
    assert com._commands_dropped == 1
    assert com._processing_errors == 0  # an expected state, not an error
    assert "Command for enocean2mqtt/dimmer not sent: transceiver offline" in caplog.text
    assert not com._pending_cmd  # the failed write un-booked its response


async def test_write_error_is_dropped_with_a_warning(caplog):
    com = _daemon()
    com._transport.send.side_effect = BrokenPipeError("peer gone")
    with caplog.at_level(logging.WARNING):
        await com._handle_mqtt("enocean2mqtt/dimmer/req", GOOD_COMMAND)
    assert com._commands_dropped == 1
    assert "transceiver offline (peer gone)" in caplog.text


async def test_secure_teach_in_while_offline_is_dropped():
    com = EnoceanDaemon(CONF, [])
    sensor = {**DIMMER, "key": "00112233445566778899AABBCCDDEEFF"}
    await com.send_secure_teach_in(sensor)  # must not raise
    assert com._commands_dropped == 1


# --- one odd telegram must not cost the transceiver connection ----------------------------------


def _telegram(marker: int):
    return RadioPacket(
        PACKET.RADIO_ERP1,
        data=[0xA5, marker, 0, 0, 0x08, 5, 0, 0, 1, 0],
        optional=[0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x40, 0x00],
    )


def _scripted_transport(com, packets, *, end_with):
    """Transport that yields *packets* on one connection, then raises *end_with*.

    Shutdown is requested on connect, so the task ends after this one connection however it ends
    (a test that hung forever in the reconnect backoff would hide the failure)."""
    connects = []

    async def connect():
        connects.append(1)
        com._shutdown.set()

    async def read_packets():
        for packet in packets:
            yield packet
        raise end_with

    com._transport = mock.AsyncMock()
    com._transport.connect = connect
    com._transport.read_packets = read_packets
    return connects


async def test_error_in_one_telegram_skips_it_and_keeps_the_connection(caplog):
    com = EnoceanDaemon(CONF, [])
    connects = _scripted_transport(
        com, [_telegram(1), _telegram(2)], end_with=ConnectionError("end of test")
    )
    handled = []

    async def handle(packet):
        if packet.data[1] == 1:
            raise IndexError("decoder bug")
        handled.append(packet.data[1])

    com._handle_enocean_packet = handle
    with caplog.at_level(logging.ERROR):
        await com._enocean_task()

    assert handled == [2]  # the telegram after the bad one was processed on the same connection
    assert len(connects) == 1
    assert com._processing_errors == 1
    assert com._transceiver_reconnects == 1  # only the scripted end, not the decoder bug
    assert "Error processing telegram" in caplog.text and "skipped" in caplog.text


async def test_connection_error_while_handling_a_telegram_still_reconnects():
    com = EnoceanDaemon(CONF, [])
    _scripted_transport(com, [_telegram(1)], end_with=ConnectionError("unused"))
    com._handle_enocean_packet = mock.AsyncMock(side_effect=BrokenPipeError("link down"))
    await com._enocean_task()
    assert com._processing_errors == 0
    assert com._transceiver_reconnects == 1


def test_stats_report_processing_errors_and_dropped_commands():
    com = EnoceanDaemon(CONF, [])
    com._processing_errors, com._commands_dropped = 2, 5
    stats = com._build_stats(60)
    assert stats["processing_errors"] == 2 and stats["commands_dropped"] == 5
