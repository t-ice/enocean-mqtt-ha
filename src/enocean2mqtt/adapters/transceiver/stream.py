"""Shared ESP3 framing for stream-based transceivers.

Both transceiver adapters (local serial + ser2net TCP) read/write ESP3 frames over an asyncio
``StreamReader``/``StreamWriter`` pair; only *how the stream opens* differs. ``StreamTransceiver``
owns the connection-agnostic part — the read buffer, ``Packet.parse_msg`` framing, ``send`` and
``close`` — and subclasses implement :meth:`connect` to populate ``_reader``/``_writer``.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator

from enocean2mqtt.protocol.constants import PARSE_RESULT
from enocean2mqtt.protocol.packet import Packet

logger = logging.getLogger("enocean2mqtt.adapters.transceiver")

_READ_CHUNK = 1024
# Resync (drop the buffer) if this much accumulates without a complete frame — bounds memory on a
# garbage/hostile stream. Far above any real ESP3 frame.
_MAX_BUFFER = 65536


class StreamTransceiver:
    """Base ESP3 transceiver over an asyncio stream (satisfies ``ports.TransceiverPort``)."""

    def __init__(self, send_interval_s: float = 0.0) -> None:
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._buffer: list[int] = []
        # Minimum wall-clock spacing between transmitted telegrams. EnOcean ERP1 sends each telegram
        # as up to 3 subtelegrams inside a ~40 ms TX window and receivers collect them over a 100 ms
        # RX maturity time; writing commands faster than that overruns the transceiver and drops
        # telegrams on bursts (e.g. "close all covers"). 0 disables pacing.
        self._send_interval = max(0.0, send_interval_s)
        self._send_lock = asyncio.Lock()
        self._next_send_at = 0.0
        self._clock = time.monotonic  # injectable for deterministic tests
        self._sleep = asyncio.sleep

    async def connect(self) -> None:  # pragma: no cover - overridden by the link adapters
        raise NotImplementedError

    async def read_packets(self) -> AsyncIterator[Packet]:
        """Yield parsed packets until the connection drops (then raises)."""
        if self._reader is None:
            raise RuntimeError("connect() must be called before read_packets()")
        while True:
            chunk = await self._reader.read(_READ_CHUNK)
            if not chunk:
                raise ConnectionError("transceiver closed the connection")
            self._buffer.extend(chunk)
            if len(self._buffer) > _MAX_BUFFER:
                # Never-completing / garbage stream — drop what we have and resync (no reconnect).
                logger.debug("transceiver buffer over %d B with no frame; resyncing", _MAX_BUFFER)
                self._buffer = []
                continue
            # Frame out every complete packet currently buffered.
            while True:
                status, self._buffer, packet = Packet.parse_msg(self._buffer)
                if status == PARSE_RESULT.INCOMPLETE:
                    break
                if status == PARSE_RESULT.OK and packet is not None:
                    yield packet
                # CRC_MISMATCH: parse_msg already advanced past the bad frame; keep going.

    async def send(self, packet: Packet) -> None:
        """Serialise and transmit *packet*, pacing bursts by ``send_interval``.

        The lock serialises concurrent senders; a monotonic deadline enforces the spacing only when
        telegrams actually bunch up, so an isolated send never waits.
        """
        if self._writer is None:
            raise RuntimeError("connect() must be called before send()")
        async with self._send_lock:
            if self._send_interval:
                wait = self._next_send_at - self._clock()
                if wait > 0:
                    await self._sleep(wait)
            self._writer.write(bytes(bytearray(packet.build())))
            await self._writer.drain()
            if self._send_interval:
                self._next_send_at = self._clock() + self._send_interval

    async def close(self) -> None:
        """Close the connection, ignoring shutdown errors."""
        if self._writer is not None:
            self._writer.close()
            with contextlib.suppress(Exception):
                await self._writer.wait_closed()
            self._reader = None
            self._writer = None
