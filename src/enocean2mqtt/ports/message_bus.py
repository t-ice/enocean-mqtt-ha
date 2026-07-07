"""Port: the MQTT message bus the application publishes to and subscribes on."""

from __future__ import annotations

from typing import Any, Protocol


class MessageBusPort(Protocol):
    """A minimal MQTT surface: build a client per (re)connect, publish/subscribe, iterate messages.

    ``publish`` is a no-op while disconnected, so callers never guard the connection.
    """

    def make_client(self) -> Any:
        """Build a fresh client (one per (re)connect attempt), with the LWT."""
        ...

    @property
    def client(self) -> Any: ...

    @client.setter
    def client(self, value: Any) -> None: ...

    @property
    def connected(self) -> bool: ...

    def messages(self) -> Any:
        """The inbound message async-iterator of the active client."""
        ...

    async def publish(self, topic: Any, payload: Any, retain: bool = False) -> None: ...

    async def subscribe(self, topic: Any) -> None: ...
