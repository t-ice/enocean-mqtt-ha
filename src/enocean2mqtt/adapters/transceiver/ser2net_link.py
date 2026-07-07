"""Remote ser2net transceiver adapter (``host:port``) via a raw TCP asyncio stream."""

from __future__ import annotations

import asyncio

from enocean2mqtt.adapters.transceiver.stream import StreamTransceiver, logger


class Ser2netLink(StreamTransceiver):
    """ESP3 transceiver over a raw TCP connection to a ser2net endpoint."""

    def __init__(self, url: str, send_interval_s: float = 0.0) -> None:
        super().__init__(send_interval_s)
        self._url = url  # normalised, e.g. "socket://192.168.10.31:3000"

    async def connect(self) -> None:
        self._buffer = []
        host, port = self._split_hostport(self._url)
        logger.info("Connecting to ser2net %s:%d", host, port)
        self._reader, self._writer = await asyncio.open_connection(host, port)

    @staticmethod
    def _split_hostport(url: str) -> tuple[str, int]:
        """Extract (host, port) from a ``socket://host:port`` (or bare ``host:port``) URL."""
        hostport = url.split("://", 1)[1] if "://" in url else url
        host, _, port = hostport.rpartition(":")
        return host, int(port)
