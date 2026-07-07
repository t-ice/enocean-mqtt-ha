"""Pick the transceiver adapter for a configured connection string."""

from __future__ import annotations

from enocean2mqtt.adapters.transceiver.ser2net_link import Ser2netLink
from enocean2mqtt.adapters.transceiver.serial_link import SerialLink
from enocean2mqtt.ports.transceiver import TransceiverPort
from enocean2mqtt.transport import is_network_port, normalize_port


def make_transceiver(connection: str, send_interval_s: float = 0.0) -> TransceiverPort:
    """A ser2net TCP link for a ``host:port``/URL connection, else a local serial link.

    *send_interval_s* paces transmitted telegrams (see ``StreamTransceiver``); 0 disables it.
    """
    if is_network_port(connection):
        return Ser2netLink(normalize_port(connection), send_interval_s)
    return SerialLink(connection, send_interval_s)
