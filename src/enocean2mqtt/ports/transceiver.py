"""Port: the EnOcean transceiver link the application reads packets from and sends packets to."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from enocean2mqtt.protocol.packet import Packet


class TransceiverOffline(ConnectionError):  # noqa: N818 - reads as a state, like ConnectionError
    """Raised by ``send`` while there is no connection (e.g. during a reconnect).

    A ``ConnectionError`` subclass, so callers that already handle a dropped link handle this too.
    """


@runtime_checkable
class TransceiverPort(Protocol):
    """A bidirectional ESP3 link to the transceiver (local serial device or ser2net TCP port)."""

    async def connect(self) -> None:
        """Open the connection (raises on failure)."""
        ...

    def read_packets(self) -> AsyncIterator[Packet]:
        """Yield parsed packets until the connection drops (then raises)."""
        ...

    async def send(self, packet: Packet) -> None:
        """Serialise and transmit *packet* (raises ``TransceiverOffline`` when not connected)."""
        ...

    async def close(self) -> None:
        """Close the connection, ignoring shutdown errors."""
        ...
