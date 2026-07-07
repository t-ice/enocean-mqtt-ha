"""Route inbound MQTT PUBLISH messages to EnOcean send requests.

Both payload forms (a topic-per-property "normal" payload and a bulk JSON payload) share the
``clear``/``learn``/``raw_data`` action vocabulary and the ``send_message`` tail. Actual
transmission is delegated to the daemon's send callable (which injects the Base ID).
"""

from __future__ import annotations

import logging

import enocean2mqtt.protocol.utils as utils

logger = logging.getLogger("enocean2mqtt.application.inbound")

# Guardrail against a buggy peer / runaway automation on the (trusted) local broker: cap how many
# distinct fields accumulate for one sensor before a send. Far above any real EEP's field count.
_MAX_ACCUMULATED_FIELDS = 256


def _decode(payload) -> str | None:
    """Decode an MQTT payload to text, or None if it isn't valid UTF-8 (a malformed publisher)."""
    try:
        return payload.decode("utf-8")
    except (UnicodeDecodeError, AttributeError):
        return None


class InboundRouter:
    """Routes inbound MQTT to EnOcean sends.

    Note: the handlers deliberately mutate the shared ``sensor`` config dict
    (``learn``/``raw_data``/``data``). This is intentional cross-message state — a
    topic-per-property command accumulates in
    ``sensor["data"]`` across several MQTT messages until a ``send``/``clear`` trigger transmits and
    resets it. Working on a private copy would break that accumulation, so the shared dict is the
    accumulator by design.
    """

    def __init__(self, sensors, send_packet, secure_teach_in=None):
        self._sensors = sensors
        # async callable (sensor, destination, command) — resolves the daemon's _send_packet.
        self._send_packet = send_packet
        # optional async callable (sensor) — sends a bidirectional secure teach-in (SEC_TI).
        self._secure_teach_in = secure_teach_in

    async def handle_normal(self, topic, payload):
        """Handle a normal (topic-per-property) payload."""
        found_topic = False
        for sensor in self._sensors:
            if sensor.name + "/" in topic:
                prop = topic[len(sensor.name + "/req/") :]
                if prop == "send":
                    found_topic = True
                    # MQTT payload is binary data, thus we need to decode it
                    text = _decode(payload)
                    if text is None:
                        logger.debug("non-UTF-8 payload on %s; ignoring", topic)
                        return found_topic
                    clear = False
                    raw_data = False
                    for action in text.lower().split("+"):
                        if action == "clear":
                            clear = True
                        elif action == "learn":
                            sensor.mark_learn()
                        elif action == "raw_data":
                            raw_data = True
                    # raw_data has not been validated by the send payload
                    if sensor.has_raw_data and not raw_data:
                        sensor.clear_raw_data()
                    await self.send_message(sensor, clear)

                elif prop == "raw_data":
                    found_topic = True
                    text = _decode(payload)
                    if text is None:
                        logger.debug("non-UTF-8 raw_data on %s; ignoring", topic)
                        return found_topic
                    sensor.set_raw_data(text)
                else:
                    found_topic = True
                    try:
                        value = int(payload)
                    except ValueError:
                        # Expected for a malformed/non-numeric payload — DEBUG, not WARNING spam.
                        logger.debug("Cannot parse int value for %s: %s", topic, payload)
                        # Prevent storing an undefined value (would raise in the EnOcean library)
                        return None
                    logger.debug("%s: %s=%s", sensor.name, prop, value)
                    data = sensor.data or {}
                    if prop not in data and len(data) >= _MAX_ACCUMULATED_FIELDS:
                        logger.debug(
                            "field cap (%d) reached for %s; dropping %s",
                            _MAX_ACCUMULATED_FIELDS,
                            sensor.name,
                            prop,
                        )
                        return found_topic
                    sensor.accumulate(prop, value)

        return found_topic

    async def handle_json(self, mqtt_topic, mqtt_json_payload):
        """Handle a bulk JSON payload sent to the '/req' topic."""
        found_topic = False
        for sensor in self._sensors:
            if sensor.name + "/" in mqtt_topic:
                prop = mqtt_topic[len(sensor.name + "/") :]
                if prop == "req":
                    found_topic = True
                    send = False
                    clear = False
                    secure_teachin = False

                    if "send" in mqtt_json_payload:
                        send = True
                        logger.debug("Send Payload: %s", mqtt_json_payload["send"])
                        for action in mqtt_json_payload["send"].lower().split("+"):
                            if action == "clear":
                                clear = True
                            elif action == "learn":
                                sensor.mark_learn()
                            elif action == "secure_teachin":
                                secure_teachin = True
                            elif action == "raw_data" and "raw_data" in mqtt_json_payload:
                                sensor.set_raw_data(mqtt_json_payload["raw_data"])
                                del mqtt_json_payload["raw_data"]
                        # 'send' is not part of the EnOcean data
                        del mqtt_json_payload["send"]

                    # Coerce remaining fields to int
                    for topic in mqtt_json_payload:
                        try:
                            mqtt_json_payload[topic] = int(mqtt_json_payload[topic])
                        except ValueError:
                            logger.debug(
                                "Cannot parse int value for %s: %s", topic, mqtt_json_payload[topic]
                            )
                            del mqtt_json_payload[topic]

                    # Append to the sensor's send buffer (keeps single topic/payload possible too).
                    logger.debug("%s: %s=%s", sensor.name, prop, mqtt_json_payload)
                    if len(sensor.data or {}) + len(mqtt_json_payload) > _MAX_ACCUMULATED_FIELDS:
                        logger.debug(
                            "field cap (%d) reached for %s; dropping bulk payload",
                            _MAX_ACCUMULATED_FIELDS,
                            sensor.name,
                        )
                    else:
                        sensor.accumulate_many(mqtt_json_payload)

                    if send is True:
                        await self.send_message(sensor, clear)
                    if secure_teachin and self._secure_teach_in is not None:
                        await self._secure_teach_in(sensor)

                # The targeted sensor has been found and handled
                break

        return found_topic

    async def send_message(self, sensor, clear):
        """Send a property-based MQTT message to EnOcean."""
        logger.debug("Trigger message to: %s", sensor.name)
        destination = utils.int_to_bytes(sensor.address)

        command = None
        command_shortcut = sensor.command
        if command_shortcut:
            if not sensor.data or not sensor.data.get(command_shortcut):
                logger.warning("Command field %s must be set in MQTT message!", command_shortcut)
                return
            command = sensor.data[command_shortcut]
            if not isinstance(command, int):
                logger.warning(
                    "Command field %s must be an integer, got %r", command_shortcut, command
                )
                return
            logger.debug("Retrieved command id from MQTT message: %s", hex(command))

        await self._send_packet(sensor, destination, command)

        if clear is True:
            logger.debug("Clearing data buffer.")
            sensor.clear_data()
        sensor.clear_learn()
        sensor.clear_raw_data()
