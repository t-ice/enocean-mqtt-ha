"""Characterization of _publish_mqtt: the RSSI/DATE aux-topic + channel-grouping + json-vs-flat
publishing policy. Locks the exact topics/payloads before the MqttPublisher extraction."""

import json
from unittest import mock

import pytest

CONF = {"mqtt_host": "localhost", "enocean_port": "socket://127.0.0.1:3000"}


@pytest.fixture
def com():
    from enocean2mqtt.application.daemon import EnoceanDaemon

    c = EnoceanDaemon(CONF, [])
    c._client = mock.Mock()
    c._client.publish = mock.AsyncMock()
    return c


def _published(com):
    """topic -> payload for every publish() await."""
    return {c.args[0]: c.args[1] for c in com._client.publish.await_args_list}


async def test_json_with_channel_grouping(com):
    """json + channel: RSSI/DATE to an aux payload on the device topic; data to a grouped topic."""
    sensor = {
        "name": "enocean2mqtt/W",
        "publish_json": "1",
        "publish_rssi": "1",
        "publish_date": "1",
        "persistent": "1",
        "channel": "ID",
    }
    mqtt_json = {"_RSSI_": -57, "_DATE_": "2026-07-03T16:00:00", "ID": 2, "SNW": 64.7}
    await com._publish_mqtt(sensor, dict(mqtt_json))
    pub = _published(com)
    # aux (RSSI + DATE) published as JSON on the bare device topic
    assert json.loads(pub["enocean2mqtt/W"]) == {"_RSSI_": -57, "_DATE_": "2026-07-03T16:00:00"}
    # data published on the channel-grouped topic (ID consumed into the topic). NOTE: _DATE_ is
    # copied into aux but NOT removed from the payload, so it rides along here too (existing quirk).
    assert json.loads(pub["enocean2mqtt/W/ID2"]) == {"_DATE_": "2026-07-03T16:00:00", "SNW": 64.7}


async def test_flat_non_json(com):
    """no publish_json: RSSI on its own subtopic, each property on name/<prop>."""
    sensor = {
        "name": "enocean2mqtt/S",
        "publish_rssi": "1",
        "persistent": "1",
    }
    mqtt_json = {"_RSSI_": -60, "_DATE_": "2026-07-03T16:00:00", "R1": 2, "EB": 1}
    await com._publish_mqtt(sensor, dict(mqtt_json))
    pub = _published(com)
    assert pub["enocean2mqtt/S/_RSSI_"] == -60
    assert pub["enocean2mqtt/S/R1"] == 2
    assert pub["enocean2mqtt/S/EB"] == 1
    # _DATE_ dropped (publish_date not set), and no bare-name aux publish in the flat path
    assert "enocean2mqtt/S" not in pub
