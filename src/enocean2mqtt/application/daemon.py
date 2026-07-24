"""this class handles the enocean and mqtt interfaces (asyncio-based)"""

import asyncio
import contextlib
import datetime
import json
import logging
import signal
import time
from collections import deque

import aiomqtt

import enocean2mqtt.protocol.utils
from enocean2mqtt.adapters.mqtt.aiomqtt_bus import AioMqttBus
from enocean2mqtt.adapters.transceiver.factory import make_transceiver
from enocean2mqtt.application.decoder import PacketDecoder
from enocean2mqtt.application.encoder import PacketEncoder
from enocean2mqtt.application.inbound import InboundRouter
from enocean2mqtt.application.publisher import MqttPublisher
from enocean2mqtt.config import as_bool
from enocean2mqtt.domain.config import Config
from enocean2mqtt.domain.sensor import Sensor
from enocean2mqtt.protocol.constants import (
    COMMON_COMMAND_CODE,
    EVENT_CODE,
    PACKET,
    RETURN_CODE,
    RORG,
)
from enocean2mqtt.protocol.packet import Packet, RadioPacket, UTETeachInPacket
from enocean2mqtt.protocol.security import (
    DEFAULT_SLF,
    SecureDevice,
    build_teach_in,
    decrypt_telegram,
    parse_slf,
    parse_teach_in,
)

# Backoff bounds (seconds) for the transceiver reconnect loop; MQTT reconnect uses the same range.
_RECONNECT_MIN_DELAY = 1
_RECONNECT_MAX_DELAY = 30
# How long the HA overlay waits for the transceiver Base ID before running discovery without it.
_BASE_ID_TIMEOUT = 10.0
# How often (seconds) the bridge/stats observability topic is (re)published.
_STATS_INTERVAL = 60.0
# Ignore absurdly large inbound MQTT payloads before parsing (defense-in-depth on the local broker).
_MAX_MQTT_PAYLOAD = 65536

logger = logging.getLogger("enocean2mqtt.application.daemon")


class _ShutdownRequested(Exception):  # noqa: N818 - control-flow signal, not an error condition
    """Raised inside the run TaskGroup to unwind the I/O tasks on SIGINT/SIGTERM."""


class EnoceanDaemon:
    """the main working class providing the MQTT interface to the enocean packet classes"""

    def __init__(self, config, sensors, *, bus=None, transceiver=None):
        """*bus* and *transceiver* are optional injection seams (for tests / alternative adapters);
        when omitted they default to the config-driven AioMqttBus / make_transceiver — i.e. the
        production wiring is unchanged."""
        # Normalise to a typed Config (also validates the mandatory keys). Accepting a raw mapping
        # keeps the many tests that construct the daemon with a plain dict working unchanged.
        self.conf = Config.from_mapping(config)
        # Normalise the device list to typed Sensor objects (idempotent for the loader/expander
        # output; also lets tests construct the daemon with plain dicts).
        self.sensors = [Sensor.from_dict(s) for s in sensors]

        # Availability (LWT): the broker publishes 'offline' if we drop; we publish 'online'
        # on connect. HA discovery configs point their availability_topic here.
        _prefix = self.conf.mqtt_prefix
        self._bridge_state_topic = _prefix + "bridge/state"
        # Observability: a retained JSON health document, republished periodically.
        self._bridge_stats_topic = _prefix + "bridge/stats"

        # MQTT gateway (the actual connect happens in run()); owns the aiomqtt client.
        self._mqtt = bus if bus is not None else self._build_mqtt_gateway()

        # setup enocean communication (local serial device or ser2net TCP, auto-detected). The send
        # interval paces command bursts so the transceiver doesn't drop telegrams (default 100 ms).
        self._transport = transceiver if transceiver is not None else self._build_transceiver()
        self._encoder = PacketEncoder(self._transport)
        # Let the encoder persist advanced outbound rolling codes via the same hook as RX.
        self._encoder.on_secure_state_change = self._notify_secure_state
        self._publisher = MqttPublisher(self._mqtt)
        # Pass a call-time-resolving send reference so overriding/patching self._send_packet works.
        self._inbound = InboundRouter(
            self.sensors,
            lambda *a, **kw: self._send_packet(*a, **kw),
            secure_teach_in=lambda s: self.send_secure_teach_in(s),
        )
        # sender will be automatically determined from the transceiver's Base ID
        self.enocean_sender = None
        # Transceiver identity from the CO_RD_VERSION response (None until known / unsupported).
        self.stick_app_version = None
        self.stick_api_version = None
        self.chip_id = None
        # Controller diagnostics (CO_RD_REPEATER / CO_RD_DUTYCYCLE_LIMIT); None until read.
        self.repeater_level = None  # 0 = off, 1 or 2 = repeater level
        self.duty_cycle_available = None  # remaining TX duty-cycle budget, percent
        # F2: duty-cycle / transmit-failed EVENTs from the transceiver (relevant once we transmit).
        self._transmit_failures = 0
        self._duty_cycle_limited = False
        # auto-respond to UTE teach-in requests (the HA overlay gates this behind its LEARN button)
        self.teach_in = True
        # Secure teach-in (0x35) reassembly buffer (per-sender: {idx: data}) + a persist hook the
        # overlay sets to durably store advanced rolling codes (None = in-memory only, e.g. tests).
        self._sec_ti_pending: dict = {}
        self.on_secure_state_change = None
        # Optional overlay (e.g. the Home Assistant bridge) that hooks into the lifecycle below via
        # before/after-connect, inbound interception and before-publish. None = plain operation.
        self.overlay = None

        # observability counters (published on the bridge/stats topic)
        self._t_start = time.monotonic()
        self._telegrams_total = 0
        self._telegrams_window = 0  # since the last stats publish; → telegrams_per_min
        self._unknown_senders = 0
        self._mqtt_reconnects = 0
        self._transceiver_reconnects = 0

        # async coordination state
        self._shutdown = asyncio.Event()
        self._base_id_ready = asyncio.Event()
        # ESP3 RESPONSE packets carry no command echo — they are correlated to the commands we sent
        # purely by order. This FIFO records what each pending response is for.
        self._pending_cmd = deque()

    def _build_transceiver(self):
        """Construct the EnOcean transceiver from config (serial or ser2net TCP, auto-detected)."""
        return make_transceiver(
            self.conf.enocean_port, send_interval_s=self.conf.send_interval_ms / 1000
        )

    def _build_mqtt_gateway(self):
        """Construct the MQTT gateway from config (incl. optional TLS); no connection yet."""
        tls_params = None
        tls_insecure = None
        if self.conf.mqtt_ssl:
            logger.info("Enabling SSL")
            tls_params = aiomqtt.TLSParameters(
                ca_certs=self.conf.mqtt_ssl_ca_certs,
                certfile=self.conf.mqtt_ssl_certfile,
                keyfile=self.conf.mqtt_ssl_keyfile,
            )
            if self.conf.mqtt_ssl_insecure:
                logger.warning("Disabling SSL certificate verification")
                tls_insecure = True
        return AioMqttBus(
            hostname=self.conf.mqtt_host,
            port=self.conf.mqtt_port,
            keepalive=self.conf.mqtt_keepalive,
            username=self.conf.mqtt_user,
            password=self.conf.mqtt_pwd,
            identifier=self.conf.mqtt_client_id,
            tls_params=tls_params,
            tls_insecure=tls_insecure,
            will_topic=self._bridge_state_topic,
        )

    # The active aiomqtt client lives on the gateway; expose it as a settable attribute for the
    # run loop (and the tests, which inject a fake client here).
    @property
    def _client(self):
        return self._mqtt.client

    @_client.setter
    def _client(self, value):
        self._mqtt.client = value

    def _make_mqtt_client(self):
        """Build a fresh aiomqtt client (delegates to the gateway)."""
        return self._mqtt.make_client()

    async def _publish(self, topic, payload, retain=False):
        """Publish to MQTT if connected (a no-op while reconnecting)."""
        await self._mqtt.publish(topic, payload, retain=retain)

    async def _subscribe(self, topic):
        """Subscribe on the active MQTT client."""
        await self._mqtt.subscribe(topic)

    # --- public service surface for an overlay (so it composes the daemon, not reaches into it) ---
    async def publish(self, topic, payload, retain=False):
        """Publish to MQTT (overlay-facing; same no-op-while-reconnecting semantics as internal)."""
        await self._publish(topic, payload, retain=retain)

    async def subscribe(self, topic):
        """Subscribe on the active MQTT client (overlay-facing)."""
        await self._subscribe(topic)

    @property
    def bus(self):
        """The MQTT gateway (message bus) this daemon publishes/subscribes through."""
        return self._mqtt

    @property
    def bridge_state_topic(self) -> str:
        """The availability (LWT) topic; an overlay points discovery availability_topic here."""
        return self._bridge_state_topic

    @property
    def base_id_ready(self):
        """asyncio.Event set once the transceiver Base ID is known (discovery waits on it)."""
        return self._base_id_ready

    # =============================================================================================
    # MQTT CLIENT
    # =============================================================================================
    async def _on_broker_connected(self):
        """Publish availability and subscribe once the broker connection is established."""
        if self.overlay is not None:
            await self.overlay.before_connect()
        logger.info("Successfully connected to MQTT broker.")
        await self._publish(self._bridge_state_topic, "online", retain=True)
        # listen to enocean send requests
        for cur_sensor in self.sensors:
            await self._subscribe(cur_sensor.name + "/req/#")
        if self.overlay is not None:
            await self.overlay.after_connect()

    async def _handle_mqtt(self, topic, payload):
        """Dispatch a PUBLISH message received from the MQTT server."""
        # An overlay may claim a message (e.g. HA system/discovery-delete topics) before dispatch.
        if self.overlay is not None and await self.overlay.intercept_inbound(topic, payload):
            return
        logger.debug("Got MQTT message: %s", topic)
        if payload is not None and len(payload) > _MAX_MQTT_PAYLOAD:
            logger.debug("MQTT payload on %s too large (%d bytes); ignoring", topic, len(payload))
            return

        # A JSON object is a structured command; anything else is treated as a plain payload.
        try:
            mqtt_payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError, ValueError):
            mqtt_payload = payload

        if isinstance(mqtt_payload, dict):
            found_topic = await self._mqtt_message_json(topic, mqtt_payload)
        else:
            found_topic = await self._mqtt_message_normal(topic, payload)

        if not found_topic:
            logger.warning("Unexpected or erroneous MQTT message: %s: %s", topic, payload)

    # =============================================================================================
    # MQTT TO ENOCEAN (thin shims over InboundRouter)
    # =============================================================================================
    async def _mqtt_message_normal(self, topic, payload):
        return await self._inbound.handle_normal(topic, payload)

    async def _mqtt_message_json(self, mqtt_topic, mqtt_json_payload):
        return await self._inbound.handle_json(mqtt_topic, mqtt_json_payload)

    async def _send_message(self, sensor, clear):
        await self._inbound.send_message(sensor, clear)

    # =============================================================================================
    # ENOCEAN TO MQTT
    # =============================================================================================
    async def _publish_mqtt(self, sensor, mqtt_json):
        """Publish decoded packet content to MQTT (delegates to MqttPublisher)"""
        if self.overlay is not None:
            await self.overlay.before_publish(sensor, mqtt_json)
        await self._publisher.publish(sensor, mqtt_json)

    async def _read_packet(self, packet, sensor):
        """interpret packet, read properties and publish to MQTT"""
        mqtt_json = {}

        # Shall the packet be published to MQTT ?
        if not packet.learn or as_bool(sensor.log_learn):
            # Store RSSI
            # Use underscore so that it is unique and doesn't
            # match a potential future EnOcean EEP field.
            mqtt_json["_RSSI_"] = packet.dBm

            # Store receive date
            # Use underscore so that it is unique and doesn't
            # match a potential future EnOcean EEP field.
            mqtt_json["_DATE_"] = packet.received.isoformat()

            # Handling received data packet. The decoder returns its own dict (or None); the daemon
            # owns the merge with the transport metadata above.
            decoded = self._handle_data_packet(packet, sensor)
            if decoded is None:
                logger.warning("message not interpretable: %s", sensor.name)
            else:
                mqtt_json.update(decoded)
                await self._publish_mqtt(sensor, mqtt_json)
        else:
            # learn request received
            logger.info("learn request not emitted to mqtt")

    def _handle_data_packet(self, packet, sensor):
        """decode a received telegram into a fresh payload dict (None if nothing decoded)"""
        return PacketDecoder.decode(packet, sensor)

    # =============================================================================================
    # LOW LEVEL FUNCTIONS
    # =============================================================================================
    async def _reply_packet(self, in_packet, sensor):
        """send enocean message as a reply to an incoming message"""
        # prepare addresses
        destination = in_packet.sender

        await self._send_packet(
            sensor,
            destination,
            negate_direction=True,
            learn_data=in_packet.data if in_packet.learn else None,
        )

    async def _send_packet(
        self, sensor, destination, command=None, negate_direction=False, learn_data=None
    ):
        """triggers sending of an enocean packet (delegates to PacketEncoder)"""
        # Without a Base ID (transceiver silent/not identified) and no per-device 'sender', the
        # encoder would fall back to a placeholder sender and emit a telegram with a bogus source
        # address — worse than not sending. Skip with a clear warning instead.
        if self.enocean_sender is None and not sensor.get("sender"):
            logger.warning(
                "Not sending to %s: no transceiver Base ID and the device has no 'sender'.",
                sensor.get("name", "?"),
            )
            return
        await self._encoder.send(
            sensor,
            destination,
            command=command,
            negate_direction=negate_direction,
            learn_data=learn_data,
            default_sender=self.enocean_sender,
        )

    def _match_sensor(self, packet):
        """Return the configured sensor matching *packet*'s address (and RORG, unless ignored)."""
        address = enocean2mqtt.protocol.utils.combine_hex(packet.sender)
        for sensor in self.sensors:
            if address == sensor.address and (
                packet.rorg == sensor.rorg or (not sensor.rorg and sensor.ignore)
            ):
                return sensor
        return None

    def _decrypt_secure_packet(self, packet):
        """Decrypt a 0x30/0x31 secure telegram to its inner telegram (or None if unhandled).

        Secure telegrams carry RORG 0x30/0x31, not the device's real RORG, so they're matched to a
        configured `security:` device by address alone, decrypted+verified via the crypto core, and
        rebuilt as the inner telegram for the normal decode path. RLC is advanced in memory (durable
        persistence is a later step).
        """
        address = enocean2mqtt.protocol.utils.combine_hex(packet.sender)
        sensor = next(
            (s for s in self.sensors if s.address == address and as_bool(s.security)), None
        )
        hexid = enocean2mqtt.protocol.utils.to_hex_string(packet.sender)
        if sensor is None or not sensor.key:
            self._unknown_senders += 1
            logger.info("secure telegram from unconfigured/unsecured sender %s", hexid)
            return None
        slf = parse_slf(int(sensor.slf) if sensor.slf is not None else DEFAULT_SLF)
        dev = SecureDevice(
            key=bytes.fromhex(sensor.key),
            rlc=int(sensor.rlc or 0),
            rlc_size=slf.rlc_size,
            rlc_tx=slf.rlc_tx,
            cmac_len=slf.cmac_len,
        )
        wire = bytes(packet.data[1:-5])  # DATA field: strip RORG + sender(4) + status(1)
        result = decrypt_telegram(dev, packet.rorg, wire)
        if result is None:
            logger.warning("secure telegram from %s failed to authenticate (dropped)", hexid)
            return None
        inner_rorg, inner_data = result
        if inner_rorg is None:  # 0x30 is RORG-less → use the device's configured RORG (e.g. F6)
            inner_rorg = sensor.rorg
        sensor["rlc"] = dev.rlc  # advanced inbound rolling code
        self._notify_secure_state(sensor)  # durably persist it (overlay hook; no-op standalone)
        new_data = [inner_rorg, *inner_data, *packet.sender, packet.data[-1]]
        return RadioPacket(PACKET.RADIO_ERP1, data=new_data, optional=packet.optional)

    def _notify_secure_state(self, sensor):
        """Tell the overlay a device's rolling code advanced, so it can persist it durably."""
        if self.on_secure_state_change is not None:
            try:
                self.on_secure_state_change(sensor)
            except Exception:
                logger.exception("secure-state persist callback failed")

    async def send_secure_teach_in(self, sensor):
        """Send our own 2-telegram secure teach-in (SEC_TI 0x35) so a device learns our key."""
        sensor = Sensor.from_dict(sensor)
        key_hex = sensor.key_snd or sensor.key
        if not key_hex:
            logger.warning("secure teach-in requested for %s but no key is configured", sensor.name)
            return
        slf = int(sensor.slf) if sensor.slf is not None else DEFAULT_SLF
        info = 0x24 if sensor.rorg == RORG.RPS else 0x20  # PTM Rocker A / non-PTM unidirectional
        msg1, msg2 = build_teach_in(info, slf, int(sensor.rlc_snd or 0), bytes.fromhex(key_hex))
        sender = (
            enocean2mqtt.protocol.utils.int_to_bytes(sensor.sender)
            if sensor.sender
            else self.enocean_sender
        ) or [0, 0, 0, 0]
        opt = [0x03, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0x00]  # subtel, broadcast dest, dBm, no security
        for body in (msg1, msg2):
            data = [RORG.SEC_TI, *body, *sender, 0x00]
            await self._transport.send(RadioPacket(PACKET.RADIO_ERP1, data=data, optional=opt))
        logger.info("sent secure teach-in for %s", sensor.name)

    async def _handle_secure_teach_in(self, packet):
        """Reassemble a 2-telegram SEC_TI (0x35) teach-in; hand it to the overlay (learn mode)."""
        if not self.teach_in:
            return  # only while learn mode is on
        hexid = enocean2mqtt.protocol.utils.to_hex_string(packet.sender)
        address = enocean2mqtt.protocol.utils.combine_hex(packet.sender)
        data = bytes(packet.data[1:-5])  # SEC_TI DATA (after RORG, before sender+status)
        if not data:
            return
        idx = (data[0] >> 6) & 0b11
        pending = self._sec_ti_pending.setdefault(address, {})
        pending[idx] = data
        if not (0 in pending and 1 in pending):
            return  # await the other telegram of the pair
        self._sec_ti_pending.pop(address, None)
        psk = bytes.fromhex(self.conf.secure_psk) if self.conf.secure_psk else None
        teach_in = parse_teach_in(pending[0], pending[1], psk=psk)
        if teach_in is None:
            logger.warning("secure teach-in from %s could not be parsed (PSK configured?)", hexid)
            return
        logger.info("secure teach-in from %s — key learned", hexid)
        if self.overlay is not None and hasattr(self.overlay, "on_secure_teach_in"):
            try:
                await self.overlay.on_secure_teach_in(teach_in, packet.sender)
            except Exception:
                logger.exception("overlay on_secure_teach_in failed")

    async def _process_radio_packet(self, packet):
        # Secure telegrams (0x30/0x31) are decrypted to their inner telegram before normal matching.
        if packet.rorg in (RORG.SEC, RORG.SEC_ENCAPS):
            packet = self._decrypt_secure_packet(packet)
            if packet is None:
                return

        # first, look whether we have this sensor configured
        matched_sensor = self._match_sensor(packet)

        # skip ignored sensors
        if matched_sensor and matched_sensor.ignore:
            return

        # log every received telegram at DEBUG (log_level: debug) — handy for finding addresses
        logger.debug("received: %s", packet)

        # abort loop if sensor not found
        if not matched_sensor:
            self._unknown_senders += 1
            logger.info(
                "unknown sensor: %s (RORG = %s)",
                enocean2mqtt.protocol.utils.to_hex_string(packet.sender),
                hex(packet.rorg),
            )
            return

        # The EnOcean library defaults learn=True; only 1BS/4BS carry a real learn bit. VLD devices
        # learn via UTE (so a non-UTE VLD telegram is data), and RPS only ever sends data telegrams.
        sensor_rorg = matched_sensor.rorg
        if (sensor_rorg == RORG.VLD and packet.rorg != RORG.UTE) or sensor_rorg == RORG.RPS:
            packet.learn = False

        # interpret packet, read properties and publish to MQTT
        await self._read_packet(packet, matched_sensor)

        # check for neccessary reply
        if as_bool(matched_sensor.answer):
            await self._reply_packet(packet, matched_sensor)

    # =============================================================================================
    # RUN LOOP (asyncio)
    # =============================================================================================
    def run(self):
        """Synchronous entry point: drive the asyncio event loop until shutdown."""
        try:
            asyncio.run(self._run_async())
        except KeyboardInterrupt:
            logger.info("Interrupted, shutting down")

    async def _run_async(self):
        """Top-level supervisor: (re)connect the MQTT broker with backoff; run the I/O tasks.

        A single event loop runs two tasks inside a TaskGroup: one reads the transceiver, one
        consumes MQTT. The transceiver task self-heals connection drops internally (so a Pi
        power-cycle / ser2net restart does not tear down MQTT); an MQTT error propagates out of
        the group and triggers a broker reconnect here — replacing the old run.sh restart loop.
        """
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            # e.g. not the main thread, or Windows — signal handlers are best-effort.
            with contextlib.suppress(NotImplementedError, RuntimeError):
                loop.add_signal_handler(sig, self._shutdown.set)

        mqtt_delay = _RECONNECT_MIN_DELAY
        while not self._shutdown.is_set():
            try:
                async with self._make_mqtt_client() as client:
                    self._client = client
                    mqtt_delay = _RECONNECT_MIN_DELAY  # connected → reset backoff
                    async with asyncio.TaskGroup() as tg:
                        tg.create_task(self._enocean_task())
                        tg.create_task(self._mqtt_task())
                        tg.create_task(self._stats_task())
                        tg.create_task(self._shutdown_watcher())
            except* _ShutdownRequested:
                logger.debug("shutdown requested")  # self._shutdown is set → loop exits below
            except* aiomqtt.MqttError as eg:
                self._mqtt_reconnects += 1
                logger.warning(
                    "MQTT connection error (%s); reconnecting in %ss",
                    eg.exceptions[0],
                    mqtt_delay,
                )
            finally:
                self._client = None

            if self._shutdown.is_set():
                break
            await asyncio.sleep(mqtt_delay)
            mqtt_delay = min(mqtt_delay * 2, _RECONNECT_MAX_DELAY)

        logger.debug("Cleaning up")
        await self._transport.close()

    async def _shutdown_watcher(self):
        """Cancel the sibling I/O tasks (via the TaskGroup) once shutdown is requested."""
        await self._shutdown.wait()
        raise _ShutdownRequested

    async def _mqtt_task(self):
        """Handle the broker side: announce availability, subscribe, consume inbound messages."""
        await self._on_broker_connected()
        async for message in self._client.messages:
            await self._handle_mqtt(message.topic.value, message.payload)

    def _build_stats(self, window_seconds):
        """Assemble the bridge/stats health document (window_seconds → telegrams_per_min)."""
        per_min = (
            round(self._telegrams_window / window_seconds * 60, 1) if window_seconds >= 1 else 0.0
        )
        base_id = (
            enocean2mqtt.protocol.utils.to_hex_string(self.enocean_sender)
            if self.enocean_sender
            else None
        )
        return {
            "uptime_s": round(time.monotonic() - self._t_start),
            "telegrams_total": self._telegrams_total,
            "telegrams_per_min": per_min,
            "unknown_senders": self._unknown_senders,
            "mqtt_reconnects": self._mqtt_reconnects,
            "transceiver_reconnects": self._transceiver_reconnects,
            "base_id": base_id,
            "stick_app_version": self.stick_app_version,
            "stick_api_version": self.stick_api_version,
            "chip_id": self.chip_id,
            "repeater_level": self.repeater_level,
            "duty_cycle_available": self.duty_cycle_available,
            "transmit_failures": self._transmit_failures,
        }

    async def _stats_task(self):
        """Periodically publish the retained bridge/stats document.

        Isolated from the transceiver/MQTT loops: a publish error is logged, never propagated, so it
        cannot tear down the TaskGroup.
        """
        # Let the startup handshake populate the transceiver identity (base_id + version) before the
        # first snapshot, so it isn't null for a whole interval — bounded, so a silent stick can't
        # delay stats indefinitely.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._base_id_ready.wait(), timeout=_BASE_ID_TIMEOUT)
        last = time.monotonic()
        while not self._shutdown.is_set():
            now = time.monotonic()
            try:
                payload = self._build_stats(now - last)
                await self._publish(self._bridge_stats_topic, json.dumps(payload), retain=True)
            except Exception as exc:
                logger.warning("failed to publish bridge stats: %s", exc)
            self._telegrams_window = 0
            last = now
            # Sleep one interval, but wake immediately on shutdown; a timeout means "publish again".
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._shutdown.wait(), timeout=_STATS_INTERVAL)

    async def _enocean_task(self):
        """Read the transceiver, reconnecting with backoff on connection loss."""
        delay = _RECONNECT_MIN_DELAY
        while not self._shutdown.is_set():
            try:
                await self._transport.connect()
                delay = _RECONNECT_MIN_DELAY  # connected → reset backoff
                await self._startup_handshake()
                async for packet in self._transport.read_packets():
                    await self._handle_enocean_packet(packet)
            except (OSError, ConnectionError) as exc:
                self._transceiver_reconnects += 1
                logger.warning("transceiver connection lost (%s); reconnecting in %ss", exc, delay)
            except Exception:
                logger.exception("unexpected transceiver error")
            finally:
                await self._transport.close()

            if self._shutdown.is_set():
                break
            await asyncio.sleep(delay)
            delay = min(delay * 2, _RECONNECT_MAX_DELAY)

    async def _startup_handshake(self):
        """Query transceiver identity + controller config after (re)connect; apply the repeater.

        ESP3 responses carry no command id, so commands go out in a fixed order recorded in
        ``self._pending_cmd`` and the read loop pops a tag per response. Each common command
        yields exactly one RESPONSE (even NOT_SUPPORTED), so the FIFO stays aligned. Reads are
        best-effort: a silent/old transceiver just leaves the field unset.
        """
        self._pending_cmd.clear()
        first = self.enocean_sender is None
        if first:
            # Identity + Base ID: only needed once (the Base ID doesn't change across reconnects).
            self._pending_cmd.append("version")
            await self._transport.send(
                Packet.create_common_command(COMMON_COMMAND_CODE.CO_RD_VERSION)
            )
            self._pending_cmd.append("idbase")
            await self._transport.send(
                Packet.create_common_command(COMMON_COMMAND_CODE.CO_RD_IDBASE)
            )
            # Apply the configured repeater once (1/2 = enable; off is the default, not written).
            want = self.conf.repeater_level
            if want:
                self._pending_cmd.append("repeater_set")
                await self._transport.send(
                    Packet.create_common_command(COMMON_COMMAND_CODE.CO_WR_REPEATER, 1, want)
                )
        # Controller diagnostics: refresh on every connect.
        self._pending_cmd.append("repeater")
        await self._transport.send(Packet.create_common_command(COMMON_COMMAND_CODE.CO_RD_REPEATER))
        self._pending_cmd.append("dutycycle")
        await self._transport.send(
            Packet.create_common_command(COMMON_COMMAND_CODE.CO_RD_DUTYCYCLE_LIMIT)
        )

    async def _handle_enocean_packet(self, packet):
        """Dispatch a packet read from the transceiver."""
        self._telegrams_total += 1
        self._telegrams_window += 1
        # Stamp arrival time (used for the _DATE_ field); the threaded reader used to do this.
        packet.received = datetime.datetime.now()

        # Auto-respond to UTE teach-in (VLD device pairing) when teach-in is enabled.
        if isinstance(packet, UTETeachInPacket) and self.teach_in:
            if self.enocean_sender is None:
                logger.debug("UTE teach-in arrived before Base ID is known; ignoring")
            else:
                response = packet.create_response_packet(self.enocean_sender)
                logger.info("Sending response to UTE teach-in.")
                await self._transport.send(response)
                # Let an overlay auto-provision the taught device (HA learn mode). Best-effort:
                # a failure here must not stop the ack/decode path.
                if self.overlay is not None and hasattr(self.overlay, "on_teach_in"):
                    try:
                        await self.overlay.on_teach_in(packet)
                    except Exception:
                        logger.exception("overlay on_teach_in failed")

        if packet.packet_type == PACKET.RADIO and getattr(packet, "rorg", None) == RORG.SEC_TI:
            await self._handle_secure_teach_in(packet)
            return

        if packet.packet_type == PACKET.RADIO:
            await self._process_radio_packet(packet)
        elif packet.packet_type == PACKET.RESPONSE:
            self._handle_response_packet(packet)
        elif packet.packet_type == PACKET.EVENT:
            self._handle_event_packet(packet)
        else:
            logger.info("got non-RF packet: %s", packet)

    def _handle_response_packet(self, packet):
        """Route an ESP3 RESPONSE to the command it answers (matched by send order)."""
        tag = self._pending_cmd.popleft() if self._pending_cmd else None
        if tag == "version":
            self._read_version_response(packet)
        elif tag == "idbase":
            self._read_base_id_response(packet)
        elif tag == "repeater":
            self._read_repeater_response(packet)
        elif tag == "dutycycle":
            self._read_dutycycle_response(packet)
        elif tag == "repeater_set":
            ok = getattr(packet, "response", None) == RETURN_CODE.OK
            logger.info("repeater configuration %s", "applied" if ok else f"rejected ({packet})")
        else:
            code = RETURN_CODE(packet.data[0]).name if packet.data else "?"
            logger.info("got response packet: %s", code)

    def _handle_event_packet(self, packet):
        """React to ESP3 EVENT packets (F2 — duty-cycle / transmit health, and controller-ready)."""
        event = getattr(packet, "event", None)
        if event == EVENT_CODE.CO_DUTYCYCLE_LIMIT:
            # The transceiver's legal TX budget is exhausted; further transmits are throttled by it
            # until the window rolls over. Surface it; actual TX back-off gating lands with P4.
            self.duty_cycle_available = 0
            self._duty_cycle_limited = True
            logger.warning("EnOcean TX duty-cycle limit reached; transmits throttled")
        elif event == EVENT_CODE.CO_TRANSMIT_FAILED:
            self._transmit_failures += 1
            logger.warning("EnOcean transmit failed (event %d total)", self._transmit_failures)
        elif event == EVENT_CODE.CO_READY:
            logger.info("transceiver reports ready")
        else:
            logger.info("got event packet: %s", packet)

    def _read_base_id_response(self, packet):
        """CO_RD_IDBASE response = return_code + 4-byte Base ID (+ optional write-cycles byte)."""
        response_data = getattr(packet, "response_data", [])
        if getattr(packet, "response", None) == RETURN_CODE.OK and len(response_data) >= 4:
            self.enocean_sender = response_data[:4]
            logger.info(
                "EnOcean transceiver Base ID: %s",
                enocean2mqtt.protocol.utils.to_hex_string(self.enocean_sender),
            )
            self._base_id_ready.set()
        else:
            logger.warning("unexpected CO_RD_IDBASE response: %s", packet)

    def _read_version_response(self, packet):
        """CO_RD_VERSION response = return_code + app(4) + api(4) + chip_id(4) + chip_ver(4) + desc.

        Best-effort: an unsupported/short response just leaves the identity fields as None.
        """
        response_data = getattr(packet, "response_data", [])
        if getattr(packet, "response", None) != RETURN_CODE.OK or len(response_data) < 16:
            logger.info("transceiver did not report a version (response: %s)", packet)
            return
        self.stick_app_version = ".".join(str(b) for b in response_data[0:4])
        self.stick_api_version = ".".join(str(b) for b in response_data[4:8])
        self.chip_id = enocean2mqtt.protocol.utils.to_hex_string(response_data[8:12])
        logger.info(
            "EnOcean transceiver: app %s, API %s, chip %s",
            self.stick_app_version,
            self.stick_api_version,
            self.chip_id,
        )

    def _read_repeater_response(self, packet):
        """CO_RD_REPEATER response = return_code + REP_ENABLE(1) + REP_LEVEL(1)."""
        rd = getattr(packet, "response_data", [])
        if getattr(packet, "response", None) == RETURN_CODE.OK and len(rd) >= 2:
            enable, level = rd[0], rd[1]
            self.repeater_level = 0 if enable == 0 else level
            logger.info(
                "EnOcean repeater: %s",
                "off" if not self.repeater_level else f"level {self.repeater_level}",
            )
        else:
            logger.debug("no/failed CO_RD_REPEATER response: %s", packet)

    def _read_dutycycle_response(self, packet):
        """CO_RD_DUTYCYCLE_LIMIT response = return_code + AVAILABLE(1, percent) + ..."""
        rd = getattr(packet, "response_data", [])
        if getattr(packet, "response", None) == RETURN_CODE.OK and rd:
            self.duty_cycle_available = rd[0]
            self._duty_cycle_limited = self.duty_cycle_available == 0
            logger.info("EnOcean TX duty-cycle available: %s%%", self.duty_cycle_available)
        else:
            logger.debug("no/failed CO_RD_DUTYCYCLE_LIMIT response: %s", packet)
