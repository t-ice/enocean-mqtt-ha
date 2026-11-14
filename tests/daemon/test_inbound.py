"""Inbound MQTT parsing (normal + JSON): the clear/learn/raw_data actions, sensor-dict mutations,
and whether a send is triggered.
"""

import logging
from unittest import mock

import pytest

from enocean2mqtt.domain.sensor import Sensor

CONF = {"mqtt_host": "localhost", "enocean_port": "socket://127.0.0.1:3000"}


def _sensor():
    # No "command" → _send_message always sends; give it what _send_message/_send_packet read.
    # A Sensor (not a plain dict) so the daemon shares this exact object and its scratch mutations
    # are observable here (from_dict returns a Sensor unchanged).
    return Sensor.from_dict(
        {
            "name": "enocean2mqtt/A",
            "address": 0xFF94CE98,
            "rorg": 0xA5,
            "func": 0x38,
            "type": 0x08,
            "sender": 0xFFAE7C90,
        }
    )


def _com(sensor):
    from enocean2mqtt.application.daemon import EnoceanDaemon

    c = EnoceanDaemon(CONF, [sensor])
    c._send_packet = mock.AsyncMock()  # observe sends without real I/O
    return c


# ---- normal (topic-based) payloads -------------------------------------------------------------


async def test_normal_send_clear_and_learn():
    sensor = _sensor()
    sensor["data"] = {"x": 1}
    com = _com(sensor)
    await com._mqtt_message_normal("enocean2mqtt/A/req/send", b"clear+learn")
    com._send_packet.assert_awaited_once()
    # learn was set then removed by _send_message; data cleared by "clear".
    assert "learn" not in sensor
    assert "data" not in sensor


async def test_normal_raw_data_stored_no_send():
    sensor = _sensor()
    com = _com(sensor)
    found = await com._mqtt_message_normal("enocean2mqtt/A/req/raw_data", b"01:00:00:09")
    assert sensor["raw_data"] == "01:00:00:09"
    com._send_packet.assert_not_awaited()
    assert found is True


async def test_normal_single_value_stored():
    sensor = _sensor()
    com = _com(sensor)
    await com._mqtt_message_normal("enocean2mqtt/A/req/SP", b"42")
    assert sensor["data"]["SP"] == 42


# ---- JSON payloads -----------------------------------------------------------------------------


async def test_json_send_with_values_and_clear():
    sensor = _sensor()
    com = _com(sensor)
    await com._mqtt_message_json("enocean2mqtt/A/req", {"send": "clear", "SP": 5})
    com._send_packet.assert_awaited_once()
    # data was populated then cleared by "clear"
    assert "data" not in sensor


async def test_json_raw_data_action():
    sensor = _sensor()
    com = _com(sensor)
    payload = {"send": "raw_data", "raw_data": "01:00:00:09"}
    await com._mqtt_message_json("enocean2mqtt/A/req", payload)
    com._send_packet.assert_awaited_once()
    # 'send' and 'raw_data' are actions, never EEP fields of the sensor data — and the caller's
    # payload dict is left untouched
    assert "send" not in (sensor.data or {}) and "raw_data" not in (sensor.data or {})
    assert payload == {"send": "raw_data", "raw_data": "01:00:00:09"}
    # raw_data was applied to the send and then consumed off the sensor by _send_message
    assert "raw_data" not in sensor


# ---- robustness: malformed / oversized input must not crash ------------------------------------


async def test_normal_send_non_utf8_payload_ignored():
    sensor = _sensor()
    com = _com(sensor)
    found = await com._mqtt_message_normal("enocean2mqtt/A/req/send", b"\xff\xfe")
    com._send_packet.assert_not_awaited()  # bad payload dropped, no crash
    assert found is True  # topic was still recognised


async def test_normal_raw_data_non_utf8_ignored():
    sensor = _sensor()
    com = _com(sensor)
    await com._mqtt_message_normal("enocean2mqtt/A/req/raw_data", b"\xff\xfe")
    assert "raw_data" not in sensor


async def test_normal_field_accumulation_capped(monkeypatch):
    from enocean2mqtt.application import inbound

    monkeypatch.setattr(inbound, "_MAX_ACCUMULATED_FIELDS", 2)
    sensor = _sensor()
    com = _com(sensor)
    for prop, val in (("A", b"1"), ("B", b"2"), ("C", b"3")):
        await com._mqtt_message_normal(f"enocean2mqtt/A/req/{prop}", val)
    assert set(sensor["data"]) == {"A", "B"}  # third field dropped at the cap


async def test_send_non_int_command_skipped():
    sensor = _sensor()
    sensor["command"] = "CMD"
    sensor["data"] = {"CMD": "notanint"}
    com = _com(sensor)
    await com._send_message(sensor, False)
    com._send_packet.assert_not_awaited()


async def test_oversized_mqtt_payload_ignored():
    sensor = _sensor()
    com = _com(sensor)
    await com._handle_mqtt("enocean2mqtt/A/req/SP", b"x" * 70000)
    assert "data" not in sensor  # never parsed


# ---- review 2026-11: malformed JSON commands are dropped field by field, never fatal -----------


@pytest.mark.parametrize(
    "payload",
    [
        {
            "EDIM": "abc",
            "send": "clear",
        },  # text: used to raise "dict changed size during iteration"
        {"EDIM": None, "send": "clear"},  # null: used to raise TypeError from int(None)
        {"EDIM": [1], "send": "clear"},  # list
        {"EDIM": {"x": 1}, "send": "clear"},  # object
        {"EDIM": "", "send": "clear"},  # empty string from a template
        {"EDIM": float("nan"), "send": "clear"},  # json.loads("NaN") yields this
    ],
)
async def test_json_bad_field_is_dropped_and_the_rest_is_sent(payload):
    sensor = _sensor()
    com = _com(sensor)
    captured = {}
    com._send_packet = mock.AsyncMock(side_effect=lambda s, *_: captured.update(s.data or {}))

    found = await com._mqtt_message_json("enocean2mqtt/A/req", {**payload, "EDIMR": 1})

    assert found is True
    com._send_packet.assert_awaited_once()
    assert captured == {"EDIMR": 1}  # only the valid field reached the telegram


@pytest.mark.parametrize("send_value", [1, None, ["clear"], {"a": 1}])
async def test_json_send_that_is_not_text_is_ignored(send_value, caplog):
    sensor = _sensor()
    com = _com(sensor)
    with caplog.at_level(logging.WARNING):
        found = await com._mqtt_message_json("enocean2mqtt/A/req", {"send": send_value, "SP": 5})
    assert found is True
    com._send_packet.assert_not_awaited()
    assert "'send' must be text" in caplog.text


async def test_json_numeric_strings_and_floats_are_accepted():
    sensor = _sensor()
    com = _com(sensor)
    captured = {}
    com._send_packet = mock.AsyncMock(side_effect=lambda s, *_: captured.update(s.data or {}))
    await com._mqtt_message_json(
        "enocean2mqtt/A/req", {"CMD": "1", "POS": 30.0, "ANG": b"127", "send": "clear"}
    )
    assert captured == {"CMD": 1, "POS": 30, "ANG": 127}


async def test_json_raw_data_that_is_not_text_is_ignored(caplog):
    sensor = _sensor()
    com = _com(sensor)
    with caplog.at_level(logging.WARNING):
        await com._mqtt_message_json("enocean2mqtt/A/req", {"send": "raw_data", "raw_data": 5})
    assert "raw_data" not in sensor
    assert "expected hex text" in caplog.text


async def test_command_id_zero_is_sent():
    """A command id of 0 is a value, not a missing field (was rejected via `not data.get(...)`)."""
    sensor = _sensor()
    sensor["command"] = "CMD"
    sensor["data"] = {"CMD": 0}
    com = _com(sensor)
    await com._send_message(sensor, False)
    com._send_packet.assert_awaited_once()
    assert com._send_packet.await_args.args[2] == 0


async def test_topics_match_the_exact_device_not_a_name_containing_it():
    """'x/eg/licht/req/…' belongs to device 'x/eg/licht', never to 'eg/licht' (substring match)."""
    from enocean2mqtt.application.daemon import EnoceanDaemon

    short = Sensor.from_dict({**_sensor().to_dict(), "name": "enocean2mqtt/eg"})
    long = Sensor.from_dict({**_sensor().to_dict(), "name": "enocean2mqtt/eg/licht"})
    com = EnoceanDaemon(CONF, [short, long])
    com._send_packet = mock.AsyncMock()

    await com._mqtt_message_normal("enocean2mqtt/eg/licht/req/SP", b"7")
    await com._mqtt_message_json("enocean2mqtt/eg/licht/req", {"EDIM": 3})

    assert long.data == {"SP": 7, "EDIM": 3}
    assert short.data is None  # nothing leaked into the device whose name is a prefix
