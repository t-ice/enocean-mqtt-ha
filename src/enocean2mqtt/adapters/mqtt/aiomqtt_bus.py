"""Async MQTT gateway — the only module that touches the ``aiomqtt`` API.

Adapter/Facade over ``aiomqtt``: builds the client (with LWT + optional TLS), owns the "active
client while connected" reference, and exposes a tiny ``publish``/``subscribe``/``messages`` surface
(publish is a no-op while disconnected, so callers never have to guard). Keeping aiomqtt behind this
one seam makes the rest of the daemon testable against a small interface.
"""

from __future__ import annotations

import logging
from typing import Any

import aiomqtt

logger = logging.getLogger("enocean2mqtt.adapters.mqtt")


class AioMqttBus:
    def __init__(
        self,
        *,
        hostname: str,
        port: int,
        keepalive: int,
        username: str | None,
        password: str | None,
        identifier: str | None,
        tls_params: aiomqtt.TLSParameters | None,
        tls_insecure: bool | None,
        will_topic: str,
    ):
        self._hostname = hostname
        self._port = port
        self._keepalive = keepalive
        self._username = username
        self._password = password
        self._identifier = identifier
        self._tls_params = tls_params
        self._tls_insecure = tls_insecure
        self._will_topic = will_topic
        # The active aiomqtt client while connected; None otherwise.
        self._client: Any = None

    def make_client(self) -> aiomqtt.Client:
        """Build a fresh aiomqtt client (one per (re)connect attempt), with the LWT."""
        return aiomqtt.Client(
            hostname=self._hostname,
            port=self._port,
            username=self._username,
            password=self._password,
            identifier=self._identifier,
            keepalive=self._keepalive,
            tls_params=self._tls_params,
            tls_insecure=self._tls_insecure,
            will=aiomqtt.Will(self._will_topic, "offline", qos=0, retain=True),
        )

    @property
    def client(self) -> Any:
        return self._client

    @client.setter
    def client(self, value: Any) -> None:
        self._client = value

    @property
    def connected(self) -> bool:
        return self._client is not None

    def messages(self):
        """The inbound message async-iterator of the active client."""
        return self._client.messages

    async def publish(self, topic, payload, retain: bool = False) -> None:
        """Publish if connected; a no-op (logged) while reconnecting."""
        if self._client is None:
            logger.debug("Dropping publish to %s: no MQTT connection", topic)
            return
        await self._client.publish(topic, payload, retain=retain)

    async def subscribe(self, topic) -> None:
        if self._client is not None:
            await self._client.subscribe(topic)
