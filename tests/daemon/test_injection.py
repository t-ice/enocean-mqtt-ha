"""The EnoceanDaemon's bus/transceiver injection seam: injected adapters are used verbatim, and
omitting them falls back to the config-driven production wiring (behavior unchanged)."""

from unittest import mock

from enocean2mqtt.application.daemon import EnoceanDaemon

CONF = {"mqtt_host": "x", "enocean_port": "socket://127.0.0.1:3000"}


def test_injected_bus_and_transceiver_are_used():
    bus = mock.Mock(name="bus")
    transceiver = mock.Mock(name="transceiver")
    com = EnoceanDaemon(CONF, [], bus=bus, transceiver=transceiver)
    assert com._mqtt is bus
    assert com._transport is transceiver


def test_defaults_build_production_adapters():
    # No injection → the config-driven AioMqttBus / make_transceiver are constructed (no I/O yet).
    com = EnoceanDaemon(CONF, [])
    assert com._mqtt is not None
    assert com._transport is not None
