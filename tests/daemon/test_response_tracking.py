"""RESPONSE bookkeeping (review 2026-11): ESP3 responses carry no command id and arrive in send
order. Every write — handshake command, radio telegram, ping — books one entry, so a telegram sent
during the startup handshake can no longer shift the handshake answers onto the wrong fields."""

from __future__ import annotations

import logging
from unittest import mock

from enocean2mqtt.application.daemon import EnoceanDaemon
from enocean2mqtt.protocol.constants import PACKET, RETURN_CODE
from enocean2mqtt.protocol.packet import ResponsePacket

CONF = {"mqtt_host": "x", "enocean_port": "socket://127.0.0.1:3000"}
ROLLO = {
    "name": "enocean2mqtt/rollo",
    "address": 0x0500_0001,
    "rorg": 0xA5,
    "func": 0x38,
    "type": 0x08,
    "sender": 0xFFAE7C81,
    "data": {"CMD": 1, "SW": 1},
}


def _response(*data):
    return ResponsePacket(PACKET.RESPONSE, data=list(data))


VERSION = _response(RETURN_CODE.OK, 2, 15, 1, 0, 2, 6, 3, 0, 1, 2, 3, 4, 0, 0, 0, 0)
IDBASE = _response(RETURN_CODE.OK, 0xFF, 0xAE, 0x7C, 0x80)
REPEATER = _response(RETURN_CODE.OK, 1, 2)  # enabled, level 2
DUTYCYCLE = _response(RETURN_CODE.OK, 87)  # 87 % available
RADIO_OK = _response(RETURN_CODE.OK)


def _daemon():
    com = EnoceanDaemon(CONF, [dict(ROLLO)])
    com._transport = mock.AsyncMock()
    return com


async def test_telegram_sent_during_the_handshake_does_not_shift_the_answers():
    """1.0.9 popped the telegram's RET_OK as the 'repeater' answer: the repeater response was then
    read as the duty cycle (0 % from REP_ENABLE) and the duty-cycle response was lost."""
    com = _daemon()
    await com._startup_handshake()  # books version, idbase, repeater, dutycycle
    await com._send_packet(com.sensors[0], [0xFF, 0xFF, 0xFF, 0xFF])  # an HA command meanwhile

    for response in (VERSION, IDBASE, REPEATER, DUTYCYCLE, RADIO_OK):
        com._handle_response_packet(response)

    assert com.enocean_sender == [0xFF, 0xAE, 0x7C, 0x80]
    assert com.repeater_level == 2
    assert com.duty_cycle_available == 87
    assert not com._pending_cmd


async def test_every_write_books_exactly_one_response_in_send_order():
    com = _daemon()
    await com._startup_handshake()
    await com._send_packet(com.sensors[0], [0xFF, 0xFF, 0xFF, 0xFF])
    assert [e.kind for e in com._pending_cmd] == [
        "version",
        "idbase",
        "repeater",
        "dutycycle",
        "radio",
    ]
    assert com._transport.send.await_count == 5


async def test_failed_write_unbooks_only_its_own_entry():
    com = _daemon()
    await com._startup_handshake()
    com._transport.send.side_effect = ConnectionError("gone")
    await com._send_packet(com.sensors[0], [0xFF, 0xFF, 0xFF, 0xFF])  # dropped, no response due
    assert [e.kind for e in com._pending_cmd] == ["version", "idbase", "repeater", "dutycycle"]


async def test_rejected_telegram_is_reported(caplog):
    """A non-OK RESPONSE to a radio telegram (busy, duty-cycle lock, …) used to be invisible."""
    com = _daemon()
    await com._send_packet(com.sensors[0], [0xFF, 0xFF, 0xFF, 0xFF])
    with caplog.at_level(logging.WARNING):
        com._handle_response_packet(_response(RETURN_CODE.ERROR))
    assert com._transmit_failures == 1
    assert "Transceiver rejected a telegram (ERROR)" in caplog.text


async def test_unknown_return_code_is_shown_as_hex(caplog):
    com = _daemon()
    with caplog.at_level(logging.INFO):
        com._handle_response_packet(_response(0x7E))  # nothing booked, unknown code
    assert "got response packet: 0x7E" in caplog.text
