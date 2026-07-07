"""Port: the EnOcean transceiver link the application reads packets from and sends packets to."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from enocean2mqtt.protocol.packet import Packet


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
        """Serialise and transmit *packet*."""
        ...

    async def close(self) -> None:
        """Close the connection, ignoring shutdown errors."""
        ...
