"""Transceiver liveness (review 2026-11): a half-open ser2net link (Pi lost power) or a hung stick
delivers nothing and raises nothing. The daemon pings a silent transceiver and reconnects when the
ping goes unanswered — before, it waited forever while the add-on still reported 'online'."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from unittest import mock

import pytest

from enocean2mqtt.adapters.transceiver.ser2net_link import Ser2netLink
from enocean2mqtt.application.daemon import EnoceanDaemon
from enocean2mqtt.protocol.constants import COMMON_COMMAND_CODE, PACKET
from enocean2mqtt.protocol.packet import Packet, ResponsePacket

CONF = {"mqtt_host": "x", "enocean_port": "socket://127.0.0.1:3000"}


class FakeTime:
    """Deterministic clock: every watchdog sleep advances it instantly."""

    def __init__(self):
        self.now = 1000.0

    def clock(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds
        await asyncio.sleep(0)  # let other tasks run


@pytest.fixture
def com():
    daemon = EnoceanDaemon(CONF, [])
    daemon._transport = mock.AsyncMock()
    fake = FakeTime()
    daemon._clock, daemon._sleep = fake.clock, fake.sleep
    daemon._last_rx = fake.now
    daemon.fake_time = fake
    return daemon


def _pings(com):
    return [
        c.args[0]
        for c in com._transport.send.await_args_list
        if c.args[0].data == [COMMON_COMMAND_CODE.CO_RD_VERSION]
    ]


async def _run_watchdog_for(com, seconds):
    task = asyncio.create_task(com._liveness_watchdog())
    while com.fake_time.now < 1000.0 + seconds and not task.done():
        await asyncio.sleep(0)
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    return task


async def test_busy_link_is_never_pinged(com):
    async def traffic():
        while True:
            com._last_rx = com.fake_time.now  # a telegram arrives at every tick
            await asyncio.sleep(0)

    feeder = asyncio.create_task(traffic())
    await _run_watchdog_for(com, 600)
    feeder.cancel()
    assert _pings(com) == []
    com._transport.close.assert_not_awaited()


async def test_silent_link_is_pinged_and_kept_when_it_answers(com):
    answered = asyncio.Event()

    async def answer_pings():
        while True:
            if _pings(com) and not answered.is_set():
                await com._handle_enocean_packet(ResponsePacket(PACKET.RESPONSE, data=[0x00]))
                answered.set()
            await asyncio.sleep(0)

    responder = asyncio.create_task(answer_pings())
    await _run_watchdog_for(com, com._idle_probe_after + 60)
    responder.cancel()
    assert len(_pings(com)) >= 1
    assert answered.is_set()
    com._transport.close.assert_not_awaited()
    assert not com._pending_cmd  # the ping's response was consumed as such


async def test_unanswered_ping_closes_the_link(com, caplog):
    with caplog.at_level(logging.WARNING):
        task = await _run_watchdog_for(com, com._idle_probe_after + com._probe_timeout + 30)
    assert len(_pings(com)) == 1
    com._transport.close.assert_awaited_once()
    assert task.done() and not task.cancelled()  # it ended itself after closing
    assert "Transceiver not responding" in caplog.text and "reconnecting" in caplog.text


async def test_ping_that_cannot_be_written_closes_the_link(com):
    com._transport.send.side_effect = BrokenPipeError("half-open")
    await _run_watchdog_for(com, com._idle_probe_after + 30)
    com._transport.close.assert_awaited_once()


async def test_half_open_tcp_link_is_detected_and_reconnected(monkeypatch):
    """End to end over a real socket: the 'Pi' accepts, answers the handshake, then goes silent
    without closing. The daemon must drop the connection and dial again."""
    monkeypatch.setattr("enocean2mqtt.application.daemon._RECONNECT_MIN_DELAY", 0)
    connections = []

    async def silent_pi(reader, writer):
        connections.append(writer)
        if len(connections) >= 2:
            daemon._shutdown.set()  # second dial = reconnected → done
        await asyncio.sleep(30)  # never answers anything, never closes (half-open)

    server = await asyncio.start_server(silent_pi, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    daemon = EnoceanDaemon({**CONF, "enocean_port": f"socket://127.0.0.1:{port}"}, [])
    assert isinstance(daemon._transport, Ser2netLink)
    daemon._idle_probe_after, daemon._probe_timeout, daemon._watchdog_tick = 0.05, 0.05, 0.01

    try:
        await asyncio.wait_for(daemon._enocean_task(), timeout=5)
    finally:
        server.close()
        for writer in connections:
            writer.close()

    assert len(connections) >= 2
    assert daemon._transceiver_reconnects >= 1


def test_ping_is_a_local_command_not_a_radio_telegram():
    """CO_RD_VERSION goes to the stick only: no radio traffic, no duty-cycle cost."""
    ping = Packet.create_common_command(COMMON_COMMAND_CODE.CO_RD_VERSION)
    assert ping.packet_type == PACKET.COMMON_COMMAND
