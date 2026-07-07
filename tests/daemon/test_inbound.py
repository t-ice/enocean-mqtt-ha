"""Inbound MQTT parsing (normal + JSON): the clear/learn/raw_data actions, sensor-dict mutations,
and whether a send is triggered.
"""

from unittest import mock

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
    # 'send' and 'raw_data' are consumed out of the payload before it becomes sensor data
    assert "send" not in payload and "raw_data" not in payload
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
