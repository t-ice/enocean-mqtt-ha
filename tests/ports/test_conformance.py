"""The adapters structurally satisfy their ports (the hexagon's contracts).

The parameter annotations double as a mypy structural check: passing each adapter where its port is
expected only type-checks if the adapter implements the Protocol.
"""

import aiomqtt

from enocean2mqtt.adapters.mqtt.aiomqtt_bus import AioMqttBus
from enocean2mqtt.adapters.transceiver.factory import make_transceiver
from enocean2mqtt.adapters.transceiver.stream import StreamTransceiver
from enocean2mqtt.ports.device_store import DeviceStorePort
from enocean2mqtt.ports.message_bus import MessageBusPort
from enocean2mqtt.ports.transceiver import TransceiverPort


def _accepts_transceiver(_t: TransceiverPort) -> None: ...
def _accepts_bus(_b: MessageBusPort) -> None: ...
def _accepts_store(_s: DeviceStorePort) -> None: ...


def test_transceiver_adapters_satisfy_port():
    t = make_transceiver("192.168.10.31:3000")
    assert isinstance(t, TransceiverPort)  # runtime_checkable Protocol
    assert isinstance(t, StreamTransceiver)
    _accepts_transceiver(t)


async def test_mqtt_gateway_satisfies_message_bus_port():
    bus = AioMqttBus(
        hostname="x",
        port=1883,
        keepalive=60,
        username=None,
        password=None,
        identifier=None,
        tls_params=None,
        tls_insecure=None,
        will_topic="e/bridge/state",
    )
    for method in ("make_client", "publish", "subscribe", "messages"):
        assert hasattr(bus, method)
    assert isinstance(bus.make_client(), aiomqtt.Client)  # aiomqtt.Client needs a running loop
    _accepts_bus(bus)


def test_sqlite_store_satisfies_device_store_port(tmp_path):
    from enocean2mqtt.adapters.store.sqlite_store import SqliteDeviceStore

    store = SqliteDeviceStore({"db_file": str(tmp_path / "db.sqlite")})
    for method in (
        "db_get_device_by_field",
        "db_list_from_fields",
        "db_upsert_device",
        "get_position",
        "set_position",
    ):
        assert hasattr(store, method)
    _accepts_store(store)
