"""Local serial transceiver adapter (``/dev/ttyUSB0``) via pyserial-asyncio."""

from __future__ import annotations

import serial_asyncio

from enocean2mqtt.adapters.transceiver.stream import StreamTransceiver, logger

_BAUDRATE = 57600


class SerialLink(StreamTransceiver):
    """ESP3 transceiver over a local serial device."""

    def __init__(self, port: str, send_interval_s: float = 0.0) -> None:
        super().__init__(send_interval_s)
        self._port = port

    async def connect(self) -> None:
        self._buffer = []
        logger.info("Opening serial device %s", self._port)
        self._reader, self._writer = await serial_asyncio.open_serial_connection(
            url=self._port, baudrate=_BAUDRATE
        )
