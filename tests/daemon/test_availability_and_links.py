"""Follow-ups from the second code review (2026-11). Each test failed before its fix.

- The bridge never reported 'offline': a clean disconnect makes the broker discard the last will.
- A broker restart closed the transceiver too, losing the telegrams of the reconnect pause.
- A peer that accepts and drops the connection was retried once per second, forever.
- One lost RESPONSE shifted every later answer onto the wrong command until the next reconnect.
- An MQTT password containing " #" was cut off; the secure PSK was written to the debug log.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from unittest import mock

import aiomqtt
import pytest

from enocean2mqtt import cli
from enocean2mqtt.adapters.transceiver import ser2net_link
from enocean2mqtt.adapters.transceiver.ser2net_link import Ser2netLink
from enocean2mqtt.application import daemon as daemon_module
from enocean2mqtt.application.daemon import EnoceanDaemon
from enocean2mqtt.application.inbound import InboundRouter
from enocean2mqtt.domain.sensor import Sensor
from enocean2mqtt.protocol.constants import COMMON_COMMAND_CODE, PACKET, RORG
from enocean2mqtt.protocol.packet import RadioPacket, ResponsePacket

CONF = {"mqtt_host": "x", "mqtt_prefix": "enocean2mqtt/", "enocean_port": "socket://127.0.0.1:3000"}
STATE = "enocean2mqtt/bridge/state"
BASE_ID_RESPONSE = [0x00, 0xFF, 0xAE, 0x7C, 0x80]
OPTIONAL = [0x03, 0xFF, 0xFF, 0xFF, 0xFF, 0x40, 0x00]


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class FakeBroker:
    """An aiomqtt client stand-in: records publishes, and whether it was left cleanly."""

    def __init__(self):
        self.published: list[tuple[str, object]] = []
        self.sessions = 0

    async def __aenter__(self):
        self.sessions += 1
        return self

    async def __aexit__(self, *exc):
        return False

    async def publish(self, topic, payload, retain=False):
        self.published.append((topic, payload))

    async def subscribe(self, topic):
        pass

    @property
    def messages(self):
        async def forever():
            await asyncio.sleep(3600)
            yield  # pragma: no cover

        return forever()

    def state(self):
        return [payload for topic, payload in self.published if topic == STATE]


def _daemon(broker=None):
    com = EnoceanDaemon(CONF, [])
    com._transport = mock.AsyncMock()
    if broker is not None:
        com._make_mqtt_client = lambda: broker
    return com


async def _park():
    await asyncio.Event().wait()  # until cancelled (not asyncio.sleep: some tests replace it)


# --- availability ---------------------------


async def test_clean_shutdown_reports_offline():
    broker = FakeBroker()
    com = _daemon(broker)
    com._enocean_task = _park
    com._stats_task = _park

    async def stop():
        while not broker.state():
            await asyncio.sleep(0)
        com._shutdown.set()

    stopper = asyncio.create_task(stop())
    await asyncio.wait_for(com._run_async(), timeout=3)
    await stopper

    assert broker.state() == ["online", "offline"]


async def test_crash_reports_offline_before_the_process_ends():
    broker = FakeBroker()
    com = _daemon(broker)
    com._enocean_task = _park
    com._stats_task = _park
    com.overlay = mock.AsyncMock()
    com.overlay.after_connect.side_effect = RuntimeError("bug in the overlay")

    with pytest.raises(ExceptionGroup):
        await asyncio.wait_for(com._run_async(), timeout=3)

    assert broker.state()[-1] == "offline"


async def test_offline_announcement_never_masks_a_lost_connection():
    client = mock.AsyncMock()
    client.publish.side_effect = aiomqtt.MqttError("not connected")
    await _daemon()._announce_offline(client)  # must not raise: the broker sends the will itself


# --- transceiver independent of the broker ---------------------------


async def test_mqtt_reconnect_leaves_the_transceiver_running(monkeypatch):
    com = _daemon()
    transceiver_starts = []
    attempts = []

    async def enocean_task():
        transceiver_starts.append(1)
        await asyncio.sleep(3600)

    class Connection:
        async def __aenter__(self):
            attempts.append(1)
            if len(attempts) < 3:
                raise aiomqtt.MqttError("broker restarting")
            com._shutdown.set()
            return mock.AsyncMock()

        async def __aexit__(self, *exc):
            return False

    com._make_mqtt_client = Connection
    com._enocean_task = enocean_task
    com._mqtt_task = _park
    com._stats_task = _park
    monkeypatch.setattr(daemon_module, "_RECONNECT_MIN_DELAY", 0)
    monkeypatch.setattr(daemon_module, "_RECONNECT_MAX_DELAY", 0)

    await asyncio.wait_for(com._run_async(), timeout=3)

    assert len(attempts) == 3
    assert len(transceiver_starts) == 1, "the transceiver task must survive broker reconnects"


async def test_lost_broker_during_a_publish_is_not_a_telegram_error(caplog):
    com = _daemon()
    com._handle_enocean_packet = mock.AsyncMock(side_effect=aiomqtt.MqttError("broker gone"))

    with caplog.at_level(logging.WARNING):
        await com._process_transceiver_packet("telegram")  # no raise: the link stays up

    assert com._processing_errors == 0
    assert "MQTT connection lost" in caplog.text
    assert "Traceback" not in caplog.text


# --- reconnect backoff ---------------------------


async def _reconnect_delays(com, monkeypatch, connection_lifetime, rounds=5):
    clock = FakeClock()
    com._clock = clock
    delays = []

    async def read_packets():
        clock.now += connection_lifetime
        raise ConnectionError("closed by peer")
        yield  # pragma: no cover

    async def sleep(delay):
        delays.append(delay)
        if len(delays) >= rounds:
            com._shutdown.set()

    com._transport.read_packets = read_packets
    com._liveness_watchdog = _park
    monkeypatch.setattr(daemon_module.asyncio, "sleep", sleep)
    await com._enocean_task()
    return delays


async def test_peer_that_accepts_then_drops_backs_off(monkeypatch):
    delays = await _reconnect_delays(_daemon(), monkeypatch, connection_lifetime=0.1)
    assert delays == [1, 2, 4, 8, 16]


async def test_backoff_starts_over_after_a_stable_connection(monkeypatch):
    delays = await _reconnect_delays(_daemon(), monkeypatch, connection_lifetime=3600)
    assert delays == [1, 1, 1, 1, 1]


async def test_mqtt_backoff_keeps_growing_while_sessions_die_at_once(monkeypatch):
    com = _daemon(FakeBroker())
    com._clock = FakeClock()
    com._mqtt_task = mock.AsyncMock(side_effect=aiomqtt.MqttError("session taken over"))
    com._stats_task = _park
    delays = []

    async def sleep(delay):
        delays.append(delay)
        if len(delays) >= 4:
            com._shutdown.set()

    monkeypatch.setattr(daemon_module.asyncio, "sleep", sleep)
    await com._mqtt_supervisor()

    assert delays == [1, 2, 4, 8]


# --- RESPONSE bookkeeping ---------------------------


async def test_overdue_response_does_not_shift_later_answers():
    com = _daemon()
    clock = FakeClock()
    com._clock = clock
    await com._transmit("a radio telegram", "radio")
    clock.now += daemon_module._RESPONSE_TIMEOUT + 1  # … its RESPONSE never came
    await com._transmit("CO_RD_IDBASE", "idbase")

    await com._handle_enocean_packet(ResponsePacket(PACKET.RESPONSE, data=BASE_ID_RESPONSE))

    assert com.enocean_sender == [0xFF, 0xAE, 0x7C, 0x80]
    assert com._responses_missed == 1
    assert not com._pending_cmd


async def test_entries_still_waiting_to_be_written_never_expire():
    com = _daemon()
    clock = FakeClock()
    com._clock = clock
    waiting = com._expect("radio")  # booked, the write is still queued behind the send pacing
    clock.now += 60

    com._expire_pending(clock.now)

    assert list(com._pending_cmd) == [waiting]


async def test_base_id_is_asked_again_when_its_answer_was_lost():
    com = _daemon()
    clock = FakeClock()
    com._clock = clock
    await com._startup_handshake()
    com._transport.send.reset_mock()

    clock.now += daemon_module._BASE_ID_RETRY + 1
    com._expire_pending(clock.now)  # the handshake's answers are overdue
    await com._retry_base_id(clock.now)

    [call] = com._transport.send.await_args_list
    assert call.args[0].data[0] == COMMON_COMMAND_CODE.CO_RD_IDBASE
    com._transport.send.reset_mock()
    await com._retry_base_id(clock.now + 1)  # a query is outstanding: not asked twice
    com._transport.send.assert_not_awaited()


async def test_base_id_is_not_asked_again_once_known():
    com = _daemon()
    await com._startup_handshake()
    com.enocean_sender = [0xFF, 0xAE, 0x7C, 0x80]
    com._pending_cmd.clear()
    com._transport.send.reset_mock()

    await com._retry_base_id(com._clock() + 3600)

    com._transport.send.assert_not_awaited()


# --- configuration ---------------------------


def _conf_file(tmp_path, *lines):
    path = tmp_path / "enocean2mqtt.conf"
    path.write_text("[CONFIG]\n" + "\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def test_password_with_hash_or_semicolon_is_kept_whole(tmp_path):
    conf = _conf_file(tmp_path, "mqtt_host = broker", "mqtt_pwd              = geheim #1 ;x")
    _sensors, config = cli.load_config_file([conf])
    assert config["mqtt_pwd"] == "geheim #1 ;x"


def test_secrets_never_reach_the_debug_log(tmp_path, caplog):
    psk = "00112233445566778899AABBCCDDEEFF"
    conf = _conf_file(tmp_path, "mqtt_pwd = geheim", f"secure_psk = {psk}")
    with caplog.at_level(logging.DEBUG):
        cli.load_config_file([conf])
    assert "Global config" in caplog.text
    assert psk not in caplog.text and "geheim" not in caplog.text


# --- small things ---------------------------


async def test_non_numeric_field_on_a_known_topic_is_not_an_unexpected_message():
    sensor = Sensor.from_dict({"name": "enocean2mqtt/dimmer", "address": 1})
    router = InboundRouter([sensor], mock.AsyncMock())
    assert await router.handle_normal("enocean2mqtt/dimmer/req/EDIM", b"abc") is True


async def test_lone_secure_teach_in_half_is_dropped_after_a_while():
    com = _daemon()
    clock = FakeClock()
    com._clock = clock
    com.overlay = mock.AsyncMock()

    def half(index):
        data = [RORG.SEC_TI, index << 6, 0x00, 0x01, 0x02, 0x03, 0x04, 0x00]
        return RadioPacket(PACKET.RADIO_ERP1, data=data, optional=OPTIONAL)

    await com._handle_secure_teach_in(half(0))
    clock.now += daemon_module._SEC_TI_WINDOW + 1
    await com._handle_secure_teach_in(half(1))  # belongs to a new attempt, not to the stale half

    com.overlay.on_secure_teach_in.assert_not_awaited()
    assert set(com._sec_ti_pending[0x01020304]) == {"at", 1}


async def test_date_carries_its_utc_offset():
    com = _daemon()
    packet = ResponsePacket(PACKET.RESPONSE, data=[0x00])
    await com._handle_enocean_packet(packet)
    assert packet.received.tzinfo is not None
    assert datetime.datetime.fromisoformat(packet.received.isoformat()).utcoffset() is not None


async def test_connect_to_a_dead_host_gives_up(monkeypatch):
    async def never(host, port):
        await asyncio.sleep(3600)

    monkeypatch.setattr(ser2net_link, "_CONNECT_TIMEOUT", 0.01)
    monkeypatch.setattr(ser2net_link.asyncio, "open_connection", never)
    with pytest.raises(OSError):  # TimeoutError is an OSError → handled by the reconnect loop
        await Ser2netLink("socket://192.0.2.1:3000").connect()


async def test_heartbeat_file_is_written_from_the_event_loop(tmp_path, monkeypatch):
    path = tmp_path / "alive"
    monkeypatch.setenv("ENOCEAN2MQTT_HEARTBEAT_FILE", str(path))
    task = asyncio.create_task(_daemon()._heartbeat_task())
    await asyncio.sleep(0.01)
    task.cancel()
    assert path.read_text().isdigit()


async def test_no_heartbeat_file_unless_configured(monkeypatch):
    monkeypatch.delenv("ENOCEAN2MQTT_HEARTBEAT_FILE", raising=False)
    await asyncio.wait_for(_daemon()._heartbeat_task(), timeout=1)  # returns at once
