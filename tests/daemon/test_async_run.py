"""Async run-loop behaviour: transceiver reconnect/backoff, Base ID handling, and the
radio-packet -> decode -> MQTT publish path end-to-end (all without real I/O)."""

from unittest import mock

import pytest

from enocean2mqtt.protocol.constants import PACKET
from enocean2mqtt.protocol.packet import RadioPacket, ResponsePacket

CONF = {"mqtt_host": "localhost", "enocean_port": "socket://127.0.0.1:3000"}


@pytest.fixture
def com():
    from enocean2mqtt.application.daemon import EnoceanDaemon

    return EnoceanDaemon(CONF, [])


async def test_enocean_task_reconnects_after_drop(com, monkeypatch):
    """A dropped transceiver connection must be retried, not kill the task."""
    monkeypatch.setattr("enocean2mqtt.application.daemon._RECONNECT_MIN_DELAY", 0)
    monkeypatch.setattr("enocean2mqtt.application.daemon._RECONNECT_MAX_DELAY", 0)

    connects = {"n": 0}

    async def fake_connect():
        connects["n"] += 1
        if connects["n"] >= 3:
            com._shutdown.set()  # stop the loop after a few reconnects

    async def fake_read_packets():
        raise ConnectionError("transceiver dropped")
        yield  # pragma: no cover - makes this an async generator

    com._transport.connect = fake_connect
    com._transport.read_packets = fake_read_packets
    com._transport.send = mock.AsyncMock()
    com._transport.close = mock.AsyncMock()

    await com._enocean_task()

    assert connects["n"] >= 3, "task should have reconnected after each drop"
    assert com._transport.close.await_count >= 3


async def test_base_id_response_sets_sender(com):
    """A CO_RD_IDBASE response populates enocean_sender and releases discovery."""
    com._pending_cmd.append("idbase")  # as _startup_handshake enqueues after sending the command
    pkt = ResponsePacket(PACKET.RESPONSE, data=[0x00, 0xFF, 0xAE, 0x7C, 0x80])  # 0x00 = OK
    assert not com._base_id_ready.is_set()

    await com._handle_enocean_packet(pkt)

    assert com.enocean_sender == [0xFF, 0xAE, 0x7C, 0x80]
    assert com._base_id_ready.is_set()


async def test_base_id_response_with_write_cycles_byte(com):
    """CO_RD_IDBASE may append a 'remaining write cycles' byte; the Base ID is still the first 4."""
    com._pending_cmd.append("idbase")
    # return_code + 4-byte base id + 0xFF remaining-write-cycles (data-len 6)
    pkt = ResponsePacket(PACKET.RESPONSE, data=[0x00, 0xFF, 0xAE, 0x7C, 0x80, 0xFF])

    await com._handle_enocean_packet(pkt)

    assert com.enocean_sender == [0xFF, 0xAE, 0x7C, 0x80]
    assert com._base_id_ready.is_set()


async def test_version_response_populates_stick_identity(com):
    """A CO_RD_VERSION response fills the stick identity fields (non-gating)."""
    com._pending_cmd.append("version")
    # RC + app(4) + api(4) + chip_id(4) + chip_ver(4) + app description (padded)
    data = [0x00, 2, 5, 3, 0, 1, 8, 0, 0, 0x01, 0x2D, 0x8C, 0x9F, 3, 1, 0, 0] + [0x00] * 16
    pkt = ResponsePacket(PACKET.RESPONSE, data=data)

    await com._handle_enocean_packet(pkt)

    assert com.stick_app_version == "2.5.3.0"
    assert com.stick_api_version == "1.8.0.0"
    assert com.chip_id == "01:2D:8C:9F"
    assert not com._base_id_ready.is_set()  # version does not gate startup


async def test_handshake_queries_identity_and_controller_config(com):
    """The startup handshake sends version, Base ID, then the repeater + duty-cycle reads, with
    matching FIFO tags. The repeater is only *written* when a level is set (see next test)."""
    from enocean2mqtt.protocol.constants import COMMON_COMMAND_CODE as CC

    com._transport.send = mock.AsyncMock()

    await com._startup_handshake()

    sent = [call.args[0].data[0] for call in com._transport.send.await_args_list]
    assert sent == [CC.CO_RD_VERSION, CC.CO_RD_IDBASE, CC.CO_RD_REPEATER, CC.CO_RD_DUTYCYCLE_LIMIT]
    assert list(com._pending_cmd) == ["version", "idbase", "repeater", "dutycycle"]


async def test_handshake_applies_configured_repeater():
    """A configured repeater level is written as CO_WR_REPEATER (enable=1 + level) on connect."""
    from enocean2mqtt.application.daemon import EnoceanDaemon
    from enocean2mqtt.protocol.constants import COMMON_COMMAND_CODE as CC

    com = EnoceanDaemon({**CONF, "repeater": "2"}, [])
    com._transport.send = mock.AsyncMock()

    await com._startup_handshake()

    wr = [
        c.args[0]
        for c in com._transport.send.await_args_list
        if c.args[0].data[0] == CC.CO_WR_REPEATER
    ]
    assert len(wr) == 1
    assert wr[0].data[1:3] == [1, 2]  # enable=1, level=2
    assert "repeater_set" in com._pending_cmd


def test_secure_packet_decrypts_to_inner(com):
    """A configured secure device: a 0x31 telegram decrypts to the inner A5 telegram."""
    from enocean2mqtt.domain.sensor import Sensor
    from enocean2mqtt.protocol.constants import RORG

    com.sensors.append(
        Sensor.from_dict(
            {
                "name": "sec",
                "address": 0x01020304,
                "security": True,
                "key": "456E4F6365616E20476D62482E313300",
                "rlc": 0xC0FFEE,
                "slf": 0x8B,  # implicit 24-bit RLC, 3-B CMAC, VAES
                "rorg": 0xA5,
                "func": 0x07,
                "type": 0x01,
            }
        )
    )
    # SEC_ENCAPS wire = enc(3EEAC4A2DF) + cmac(EAF20E); sender 01020304, status 00.
    wire = bytes.fromhex("3EEAC4A2DFEAF20E")
    data = [RORG.SEC_ENCAPS, *wire, 0x01, 0x02, 0x03, 0x04, 0x00]
    opt = [0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x40, 0x00]  # subtel, broadcast dest, dBm, security
    pkt = RadioPacket(1, data=data, optional=opt)

    inner = com._decrypt_secure_packet(pkt)

    assert inner is not None
    assert inner.rorg == 0xA5
    assert list(inner.data[1:5]) == [0x08, 0x27, 0xFF, 0x80]  # decrypted inner DATA
    assert com.sensors[-1]["rlc"] == 0xC0FFEF  # rolling code advanced + persisted on the sensor


def test_secure_packet_unknown_sender_dropped(com):
    from enocean2mqtt.protocol.constants import RORG

    data = [RORG.SEC_ENCAPS, *bytes.fromhex("3EEAC4A2DFEAF20E"), 0x01, 0x02, 0x03, 0x04, 0x00]
    opt = [0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x40, 0x00]
    pkt = RadioPacket(1, data=data, optional=opt)
    assert com._decrypt_secure_packet(pkt) is None  # no configured secure device → dropped


async def test_secure_teach_in_reassembly_notifies_overlay(com):
    """Two SEC_TI (0x35) telegrams reassemble into a TeachIn handed to the overlay (learn mode)."""
    from enocean2mqtt.protocol.constants import RORG
    from enocean2mqtt.protocol.security import build_teach_in

    com.teach_in = True
    com.overlay = mock.Mock()
    com.overlay.on_secure_teach_in = mock.AsyncMock()
    key = bytes.fromhex("456E4F6365616E20476D62482E313300")
    m1, m2 = build_teach_in(0x24, 0x8B, 0x3E2D00, key)
    opt = [0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x40, 0x00]
    for body in (m1, m2):
        data = [RORG.SEC_TI, *body, 0x01, 0x02, 0x03, 0x04, 0x00]
        await com._handle_enocean_packet(RadioPacket(1, data=data, optional=opt))

    com.overlay.on_secure_teach_in.assert_awaited_once()
    teach_in = com.overlay.on_secure_teach_in.await_args.args[0]
    assert teach_in.key == key and teach_in.rlc == 0x3E2D00 and teach_in.ptm is True


async def test_send_secure_teach_in_emits_two_telegrams(com):
    from enocean2mqtt.domain.sensor import Sensor
    from enocean2mqtt.protocol.constants import RORG

    com._transport.send = mock.AsyncMock()
    com.enocean_sender = [0xFF, 0xAA, 0xBB, 0xCC]
    sensor = Sensor.from_dict(
        {
            "name": "sec",
            "address": 0x05000001,
            "rorg": 0xF6,
            "func": 0x02,
            "type": 0x01,
            "security": True,
            "key": "456E4F6365616E20476D62482E313300",
            "rlc_snd": 0x100,
            "slf": 0x8B,
        }
    )
    await com.send_secure_teach_in(sensor)
    sent = [c.args[0] for c in com._transport.send.await_args_list]
    assert len(sent) == 2
    assert all(p.rorg == RORG.SEC_TI for p in sent)


def test_encoder_wrap_secure_roundtrip():
    """The encoder's secure-wrap produces a 0x31 telegram that decrypts back to the plaintext."""
    from enocean2mqtt.application.encoder import PacketEncoder
    from enocean2mqtt.domain.sensor import Sensor
    from enocean2mqtt.protocol.security import SecureDevice, decrypt_telegram

    enc = PacketEncoder(None)
    key_hex = "456E4F6365616E20476D62482E313300"
    sensor = Sensor.from_dict(
        {
            "name": "x",
            "address": 0x05000001,
            "security": True,
            "key": key_hex,
            "rlc_snd": 0x001000,
            "slf": 0x8B,
        }
    )
    plain = RadioPacket(
        1,
        data=[0xA5, 0x08, 0x27, 0xFF, 0x80, 0xFF, 0xAA, 0xBB, 0xCC, 0x00],
        optional=[0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x40, 0x00],
    )
    wrapped = enc._wrap_secure(plain, sensor)
    assert wrapped.rorg == 0x31
    rx = SecureDevice(
        key=bytes.fromhex(key_hex), rlc=0x001000, rlc_size=3, rlc_tx=False, cmac_len=3
    )
    inner = decrypt_telegram(rx, 0x31, bytes(wrapped.data[1:-5]))
    assert inner == (0xA5, bytes.fromhex("0827FF80"))
    assert sensor["rlc_snd"] == 0x001001  # outbound RLC advanced


async def test_send_skipped_without_base_id_and_no_sender(com, caplog):
    """No Base ID + a device with no 'sender' → the send is skipped (no placeholder telegram)."""
    import logging

    com.enocean_sender = None
    com._encoder.send = mock.AsyncMock()
    with caplog.at_level(logging.WARNING):
        await com._send_packet({"name": "x", "address": 0x05000001}, [0xFF, 0xFF, 0xFF, 0xFF])
    com._encoder.send.assert_not_awaited()
    assert "Base ID" in caplog.text and "x" in caplog.text


async def test_send_proceeds_with_base_id(com):
    """With a Base ID known, the send is delegated to the encoder."""
    com.enocean_sender = [0xFF, 0xAE, 0x7C, 0x80]
    com._encoder.send = mock.AsyncMock()
    await com._send_packet({"name": "x", "address": 0x05000001}, [0xFF, 0xFF, 0xFF, 0xFF])
    com._encoder.send.assert_awaited_once()


async def test_secure_tx_skips_non_securable_rorg(monkeypatch):
    """A secure device sending a non-securable RORG (0xD0 signal) transmits it un-wrapped."""
    from enocean2mqtt.application.encoder import PacketEncoder

    enc = PacketEncoder(mock.Mock())
    enc._transport.send = mock.AsyncMock()
    stub = RadioPacket(
        1,
        data=[0xD0, 0x01, 0xFF, 0xAA, 0xBB, 0xCC, 0x00],
        optional=[0x01, 0xFF, 0xFF, 0xFF, 0xFF, 0x40, 0x00],
    )
    monkeypatch.setattr(RadioPacket, "create", staticmethod(lambda *a, **k: stub))
    monkeypatch.setattr(PacketEncoder, "_apply_default_and_data", lambda self, p, s: None)
    monkeypatch.setattr(
        PacketEncoder,
        "_wrap_secure",
        mock.Mock(side_effect=AssertionError("0xD0 must not be secure-wrapped")),
    )
    sensor = {
        "name": "sig",
        "address": 0x05000002,
        "security": True,
        "key": "456E4F6365616E20476D62482E313300",
    }
    await enc.send(sensor, destination=[0xFF, 0xAA, 0xBB, 0xCC])
    sent = enc._transport.send.await_args.args[0]
    assert sent.data[0] == 0xD0  # transmitted as plaintext, not wrapped to 0x30/0x31


async def test_ute_teach_in_notifies_overlay(com):
    """An accepted UTE teach-in (learn mode on) is surfaced to the overlay's on_teach_in hook."""
    from enocean2mqtt.protocol.packet import Packet

    # A real UTE teach-in frame (D2-01-01 from sender 01:94:E3:B9), from the conformance test.
    _s, _b, pkt = Packet.parse_msg(
        bytearray(
            [
                0x55,
                0x00,
                0x0D,
                0x07,
                0x01,
                0xFD,
                0xD4,
                0xA0,
                0xFF,
                0x3E,
                0x00,
                0x01,
                0x01,
                0xD2,
                0x01,
                0x94,
                0xE3,
                0xB9,
                0x00,
                0x01,
                0xFF,
                0xFF,
                0xFF,
                0xFF,
                0x40,
                0x00,
                0xAB,
            ]
        )
    )
    com.enocean_sender = [0xDE, 0xAD, 0xBE, 0xEF]
    com.teach_in = True
    com._transport.send = mock.AsyncMock()
    com.overlay = mock.Mock()
    com.overlay.on_teach_in = mock.AsyncMock()

    await com._handle_enocean_packet(pkt)

    com.overlay.on_teach_in.assert_awaited_once_with(pkt)


async def test_repeater_response_parsed(com):
    """CO_RD_REPEATER response (enable + level) fills repeater_level; enable=0 → off (0)."""
    com._pending_cmd.append("repeater")
    await com._handle_enocean_packet(ResponsePacket(PACKET.RESPONSE, data=[0x00, 0x01, 0x02]))
    assert com.repeater_level == 2

    com._pending_cmd.append("repeater")
    await com._handle_enocean_packet(ResponsePacket(PACKET.RESPONSE, data=[0x00, 0x00, 0x01]))
    assert com.repeater_level == 0


async def test_dutycycle_response_parsed(com):
    """CO_RD_DUTYCYCLE_LIMIT response = OK + available-percent byte."""
    com._pending_cmd.append("dutycycle")
    await com._handle_enocean_packet(ResponsePacket(PACKET.RESPONSE, data=[0x00, 0x2A]))
    assert com.duty_cycle_available == 42


async def test_dutycycle_limit_event_flags_throttle(com):
    """A CO_DUTYCYCLE_LIMIT EVENT marks the transceiver as duty-cycle throttled."""
    from enocean2mqtt.protocol.constants import EVENT_CODE
    from enocean2mqtt.protocol.packet import EventPacket

    evt = EventPacket(PACKET.EVENT, data=[EVENT_CODE.CO_DUTYCYCLE_LIMIT])
    await com._handle_enocean_packet(evt)
    assert com._duty_cycle_limited is True
    assert com.duty_cycle_available == 0


async def test_transmit_failed_event_counts(com):
    """A CO_TRANSMIT_FAILED EVENT increments the transmit-failure counter."""
    from enocean2mqtt.protocol.constants import EVENT_CODE
    from enocean2mqtt.protocol.packet import EventPacket

    for _ in range(2):
        evt = EventPacket(PACKET.EVENT, data=[EVENT_CODE.CO_TRANSMIT_FAILED])
        await com._handle_enocean_packet(evt)
    assert com._transmit_failures == 2


async def test_radio_packet_decodes_and_publishes():
    """A radio telegram from a configured sensor is decoded and published to MQTT."""
    from enocean2mqtt.application.daemon import EnoceanDaemon

    sensor = {
        "name": "enocean2mqtt/ERR",
        "address": 0x058E4FA7,
        "rorg": 0xA5,
        "func": 0x10,
        "type": 0x03,
        "command": "",
        "direction": "",
        "publish_json": "1",  # as the HA overlay configures sensors
    }
    com = EnoceanDaemon(CONF, [sensor])
    com._client = mock.Mock()
    com._client.publish = mock.AsyncMock()

    # Real A5-10-03 room-controller telegram (sender 05:8E:4F:A7 -> address above).
    packet = RadioPacket(
        1,
        data=[0xA5, 0x00, 0xA2, 0x76, 0x0F, 0x05, 0x8E, 0x4F, 0xA7, 0x80],
        optional=[0, 255, 255, 255, 255, 0x41, 0],
    )
    await com._handle_enocean_packet(packet)

    # A JSON payload carrying the decoded setpoint/temperature was published to the sensor topic.
    published = {c.args[0]: c.args[1] for c in com._client.publish.await_args_list}
    assert "enocean2mqtt/ERR" in published
    assert "SP" in published["enocean2mqtt/ERR"] and "TMP" in published["enocean2mqtt/ERR"]


async def test_build_stats_reports_counters_and_identity(com):
    """_build_stats snapshots the counters + transceiver identity for the bridge/stats topic."""
    com._telegrams_total = 120
    com._telegrams_window = 30  # over a 60s window → 30/min
    com._unknown_senders = 2
    com._mqtt_reconnects = 1
    com._transceiver_reconnects = 3
    com.enocean_sender = [0xFF, 0xAE, 0x7C, 0x80]
    com.stick_app_version = "2.5.3.0"
    com.chip_id = "01:2D:8C:9F"

    stats = com._build_stats(window_seconds=60)

    assert stats["telegrams_total"] == 120
    assert stats["telegrams_per_min"] == 30.0
    assert stats["unknown_senders"] == 2
    assert stats["mqtt_reconnects"] == 1
    assert stats["transceiver_reconnects"] == 3
    assert stats["base_id"] == "FF:AE:7C:80"
    assert stats["stick_app_version"] == "2.5.3.0"
    assert stats["chip_id"] == "01:2D:8C:9F"
    assert stats["uptime_s"] >= 0


async def test_stats_task_publishes_retained_and_resets_window(com, monkeypatch):
    """The stats task publishes retained JSON to bridge/stats and resets the per-window counter."""
    import json

    monkeypatch.setattr("enocean2mqtt.application.daemon._STATS_INTERVAL", 0.01)
    com._base_id_ready.set()  # handshake done → stats task skips its initial bounded wait
    com._telegrams_window = 5
    published = []

    async def fake_publish(topic, payload, retain=False):
        published.append((topic, payload, retain))
        com._shutdown.set()  # stop after the first publish

    com._publish = fake_publish
    await com._stats_task()

    assert len(published) == 1
    topic, payload, retain = published[0]
    assert topic == com._bridge_stats_topic
    assert retain is True
    assert json.loads(payload)["telegrams_total"] == com._telegrams_total
    assert com._telegrams_window == 0  # reset for the next window


# --- UTE teach-in auto-response + Base ID edge + SSL config + the MQTT run loop ----------------

import asyncio  # noqa: E402

import aiomqtt  # noqa: E402

_UTE_BYTES = bytes(
    [
        0x55,
        0x00,
        0x0D,
        0x07,
        0x01,
        0xFD,
        0xD4,
        0xA0,
        0xFF,
        0x3E,
        0x00,
        0x01,
        0x01,
        0xD2,
        0x01,
        0x94,
        0xE3,
        0xB9,
        0x00,
        0x01,
        0xFF,
        0xFF,
        0xFF,
        0xFF,
        0x40,
        0x00,
        0xAB,
    ]
)


def _ute_packet():
    from enocean2mqtt.protocol.packet import Packet

    return Packet.parse_msg(_UTE_BYTES)[2]


async def test_ute_teach_in_sends_response_when_enabled(com):
    com.teach_in = True
    com.enocean_sender = [0xDE, 0xAD, 0xBE, 0xEF]
    com._transport = mock.AsyncMock()
    await com._handle_enocean_packet(_ute_packet())
    com._transport.send.assert_awaited()  # a UTE response was transmitted


async def test_ute_teach_in_silent_when_disabled(com):
    com.teach_in = False
    com.enocean_sender = [0xDE, 0xAD, 0xBE, 0xEF]
    com._transport = mock.AsyncMock()
    await com._handle_enocean_packet(_ute_packet())
    com._transport.send.assert_not_awaited()  # no response while teach-in is off


async def test_ute_teach_in_skipped_before_base_id(com):
    com.teach_in = True
    com.enocean_sender = None  # Base ID not yet known -> must not crash on create_response_packet
    com._transport = mock.AsyncMock()
    await com._handle_enocean_packet(_ute_packet())
    com._transport.send.assert_not_awaited()


async def test_base_id_response_ignored_when_already_known(com):
    com.enocean_sender = [0x11, 0x22, 0x33, 0x44]  # already known
    pkt = ResponsePacket(PACKET.RESPONSE, data=[0x00, 0xAA, 0xBB, 0xCC, 0xDD])
    await com._handle_enocean_packet(pkt)
    assert com.enocean_sender == [0x11, 0x22, 0x33, 0x44]  # unchanged


def test_ssl_config_builds_tls_gateway():
    from enocean2mqtt.application.daemon import EnoceanDaemon

    conf = {
        **CONF,
        "mqtt_ssl": "true",
        "mqtt_ssl_insecure": "true",
        "mqtt_ssl_ca_certs": "/x/ca.pem",
    }
    com = EnoceanDaemon(conf, [])
    assert com._mqtt._tls_params is not None and com._mqtt._tls_insecure is True


async def test_run_async_exits_cleanly_on_shutdown(com, monkeypatch):
    com._shutdown.set()  # request shutdown up front → the watcher unwinds the group
    cm = mock.AsyncMock()
    cm.__aenter__ = mock.AsyncMock(return_value=mock.AsyncMock())
    cm.__aexit__ = mock.AsyncMock(return_value=False)
    monkeypatch.setattr(com, "_make_mqtt_client", lambda: cm)
    monkeypatch.setattr(com, "_enocean_task", mock.AsyncMock())
    monkeypatch.setattr(com, "_mqtt_task", mock.AsyncMock())
    com._transport = mock.AsyncMock()
    await asyncio.wait_for(com._run_async(), timeout=2)
    com._transport.close.assert_awaited()


async def test_run_async_reconnects_on_mqtt_error(com, monkeypatch):
    attempts = {"n": 0}

    class CM:
        async def __aenter__(self):
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise aiomqtt.MqttError("connection refused")
            com._shutdown.set()  # second attempt succeeds then we stop
            return mock.AsyncMock()

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(com, "_make_mqtt_client", lambda: CM())
    monkeypatch.setattr(com, "_enocean_task", mock.AsyncMock())
    monkeypatch.setattr(com, "_mqtt_task", mock.AsyncMock())
    com._transport = mock.AsyncMock()
    slept = []
    monkeypatch.setattr(asyncio, "sleep", mock.AsyncMock(side_effect=lambda d: slept.append(d)))
    await asyncio.wait_for(com._run_async(), timeout=2)
    assert attempts["n"] == 2 and slept and slept[0] == 1  # backoff after the MQTT error
