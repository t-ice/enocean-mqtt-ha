"""EnoceanDaemon radio-packet routing: sensor matching, ignore, learn-filtering, RPS/VLD, reply."""

import datetime
import types
from unittest import mock

from enocean2mqtt.application.daemon import EnoceanDaemon
from enocean2mqtt.protocol.constants import RORG

CONF = {"mqtt_host": "x", "enocean_port": "socket://127.0.0.1:3000"}


def _com(sensors):
    com = EnoceanDaemon(CONF, sensors)
    com._publish_mqtt = mock.AsyncMock()
    com._send_packet = mock.AsyncMock()
    # decode "succeeds" (returns a payload dict) unless a test overrides it
    com._handle_data_packet = mock.Mock(return_value={"TMP": 21.5})
    return com


def _packet(sender, rorg, *, learn=False):
    return types.SimpleNamespace(
        sender=sender,
        rorg=rorg,
        learn=learn,
        dBm=-60,
        received=datetime.datetime(2026, 7, 4, 12, 0, 0),
    )


async def test_matched_sensor_is_decoded_and_published():
    com = _com([{"name": "e/w", "address": 0x059ED79A, "rorg": 0xA5, "func": 0x13, "type": 0x01}])
    await com._process_radio_packet(_packet([0x05, 0x9E, 0xD7, 0x9A], 0xA5))
    com._handle_data_packet.assert_called_once()
    com._publish_mqtt.assert_awaited_once()


async def test_unknown_sender_is_dropped():
    com = _com([{"name": "e/w", "address": 0x059ED79A, "rorg": 0xA5}])
    await com._process_radio_packet(_packet([0xDE, 0xAD, 0xBE, 0xEF], 0xA5))
    com._publish_mqtt.assert_not_awaited()


async def test_ignored_sensor_is_dropped():
    com = _com([{"name": "e/echo", "address": 0xFFAE7C81, "ignore": 1}])  # no rorg → echo-suppress
    await com._process_radio_packet(_packet([0xFF, 0xAE, 0x7C, 0x81], 0xF6))
    com._publish_mqtt.assert_not_awaited()


async def test_learn_packet_suppressed_unless_log_learn():
    com = _com([{"name": "e/t", "address": 0x01020304, "rorg": 0xA5, "func": 0x02, "type": 0x05}])
    await com._process_radio_packet(_packet([0x01, 0x02, 0x03, 0x04], 0xA5, learn=True))
    com._publish_mqtt.assert_not_awaited()  # 4BS learn telegram not published

    com2 = _com(
        [
            {
                "name": "e/t",
                "address": 0x01020304,
                "rorg": 0xA5,
                "func": 0x02,
                "type": 0x05,
                "log_learn": "true",
            }
        ]
    )
    await com2._process_radio_packet(_packet([0x01, 0x02, 0x03, 0x04], 0xA5, learn=True))
    com2._publish_mqtt.assert_awaited_once()


async def test_rps_forces_learn_false_so_buttons_publish():
    com = _com(
        [{"name": "e/btn", "address": 0xFEE25DBA, "rorg": RORG.RPS, "func": 0x02, "type": 0x01}]
    )
    # even though the packet arrives with learn=True, RPS is forced to data → published
    await com._process_radio_packet(_packet([0xFE, 0xE2, 0x5D, 0xBA], RORG.RPS, learn=True))
    com._publish_mqtt.assert_awaited_once()


async def test_answer_sensor_triggers_reply():
    com = _com(
        [
            {
                "name": "e/a",
                "address": 0x01020304,
                "rorg": 0xA5,
                "func": 0x02,
                "type": 0x05,
                "answer": "true",
            }
        ]
    )
    com._reply_packet = mock.AsyncMock()
    await com._process_radio_packet(_packet([0x01, 0x02, 0x03, 0x04], 0xA5))
    com._reply_packet.assert_awaited_once()


async def test_not_interpretable_logs_and_skips_publish(caplog):
    com = _com([{"name": "e/t", "address": 0x01020304, "rorg": 0xA5, "func": 0x02, "type": 0x05}])
    com._handle_data_packet = mock.Mock(return_value=None)  # decode found nothing
    await com._process_radio_packet(_packet([0x01, 0x02, 0x03, 0x04], 0xA5))
    com._publish_mqtt.assert_not_awaited()
