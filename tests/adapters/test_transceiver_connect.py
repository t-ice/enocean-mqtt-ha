"""Transceiver adapters' connect() paths (success + failure) and stream close() error handling."""

from unittest import mock

import pytest

from enocean2mqtt.adapters.transceiver.ser2net_link import Ser2netLink
from enocean2mqtt.adapters.transceiver.serial_link import SerialLink


async def test_serial_link_connect_opens_serial():
    reader, writer = mock.Mock(), mock.Mock()
    link = SerialLink("/dev/ttyUSB0")
    with mock.patch(
        "serial_asyncio.open_serial_connection", new=mock.AsyncMock(return_value=(reader, writer))
    ) as opener:
        await link.connect()
    opener.assert_awaited_once()
    assert opener.await_args.kwargs["url"] == "/dev/ttyUSB0"
    assert opener.await_args.kwargs["baudrate"] == 57600
    assert link._reader is reader and link._writer is writer


async def test_serial_link_connect_propagates_error():
    link = SerialLink("/dev/ttyUSB0")
    with (
        mock.patch(
            "serial_asyncio.open_serial_connection",
            new=mock.AsyncMock(side_effect=FileNotFoundError),
        ),
        pytest.raises(FileNotFoundError),
    ):
        await link.connect()


async def test_ser2net_link_connect_opens_tcp():
    reader, writer = mock.Mock(), mock.Mock()
    link = Ser2netLink("socket://192.168.10.31:3000")
    with mock.patch(
        "asyncio.open_connection", new=mock.AsyncMock(return_value=(reader, writer))
    ) as opener:
        await link.connect()
    opener.assert_awaited_once_with("192.168.10.31", 3000)
    assert link._reader is reader and link._writer is writer


async def test_ser2net_link_connect_propagates_error():
    link = Ser2netLink("socket://192.168.10.31:3000")
    with (
        mock.patch(
            "asyncio.open_connection", new=mock.AsyncMock(side_effect=ConnectionRefusedError)
        ),
        pytest.raises(ConnectionRefusedError),
    ):
        await link.connect()


async def test_close_swallows_wait_closed_error():
    """Closing a dead socket must not raise (the reconnect loop relies on this)."""
    link = Ser2netLink("socket://h:3000")
    writer = mock.Mock()
    writer.wait_closed = mock.AsyncMock(side_effect=OSError("already gone"))
    link._writer = writer
    await link.close()  # must not raise
    writer.close.assert_called_once()
    assert link._writer is None and link._reader is None


async def test_read_and_send_require_connect_first():
    """Guards survive `python -O` (no bare asserts): explicit RuntimeError before connect()."""
    link = Ser2netLink("socket://h:3000")
    with pytest.raises(RuntimeError, match="connect"):
        async for _ in link.read_packets():
            break
    with pytest.raises(RuntimeError, match="connect"):
        await link.send(None)


async def test_read_buffer_resyncs_on_overflow(monkeypatch):
    """A garbage/never-completing stream is bounded: over the cap, drop the buffer and resync."""
    from enocean2mqtt.adapters.transceiver import stream as stream_mod

    monkeypatch.setattr(stream_mod, "_MAX_BUFFER", 8)
    link = Ser2netLink("socket://h:3000")
    link._reader = mock.Mock()
    # 20 junk bytes (no 0x55 sync) exceed the cap, then EOF ends the loop.
    link._reader.read = mock.AsyncMock(side_effect=[b"\x00" * 20, b""])
    with pytest.raises(ConnectionError):
        async for _ in link.read_packets():
            pass
    assert link._buffer == []  # cleared on overflow, not grown
