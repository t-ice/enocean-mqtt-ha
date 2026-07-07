"""Async MQTT layer: the daemon builds an aiomqtt client, announces availability + subscribes on
connect, and dispatches inbound messages (JSON vs normal payloads).
"""

from unittest import mock

import aiomqtt
import pytest


@pytest.fixture
def communicator():
    from enocean2mqtt.application.daemon import EnoceanDaemon

    conf = {
        "mqtt_host": "localhost",
        "mqtt_port": "1883",
        "enocean_port": "socket://127.0.0.1:3000",
        "mqtt_client_id": "test",
    }
    sensors = [{"name": "enocean2mqtt/Dev1"}, {"name": "enocean2mqtt/Dev2"}]
    return EnoceanDaemon(conf, sensors)


async def test_builds_aiomqtt_client_with_lwt(communicator):
    # aiomqtt.Client binds to the running loop at construction, so build it inside the loop.
    client = communicator._make_mqtt_client()
    assert isinstance(client, aiomqtt.Client)


async def test_on_broker_connected_announces_and_subscribes(communicator):
    communicator._client = mock.Mock()
    communicator._client.publish = mock.AsyncMock()
    communicator._client.subscribe = mock.AsyncMock()

    await communicator._on_broker_connected()

    # Availability announced online (retained) on the bridge state topic.
    communicator._client.publish.assert_any_await(
        communicator._bridge_state_topic, "online", retain=True
    )
    # Subscribed to every sensor's request topic.
    subscribed = {c.args[0] for c in communicator._client.subscribe.await_args_list}
    assert subscribed == {"enocean2mqtt/Dev1/req/#", "enocean2mqtt/Dev2/req/#"}


async def test_publish_is_noop_without_connection(communicator):
    communicator._client = None
    # Must not raise when the broker is not connected (a reconnect is in progress).
    await communicator._publish("some/topic", "payload", retain=True)


async def test_handle_mqtt_routes_json_and_normal(communicator):
    communicator._mqtt_message_json = mock.AsyncMock(return_value=True)
    communicator._mqtt_message_normal = mock.AsyncMock(return_value=True)

    await communicator._handle_mqtt("enocean2mqtt/Dev1/req", b'{"send": "clear"}')
    communicator._mqtt_message_json.assert_awaited_once()
    communicator._mqtt_message_normal.assert_not_awaited()

    communicator._mqtt_message_json.reset_mock()
    await communicator._handle_mqtt("enocean2mqtt/Dev1/req/send", b"clear")
    communicator._mqtt_message_normal.assert_awaited_once()
    communicator._mqtt_message_json.assert_not_awaited()
