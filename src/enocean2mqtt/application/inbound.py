"""Route inbound MQTT PUBLISH messages to EnOcean send requests.

Both payload forms (a topic-per-property "normal" payload and a bulk JSON payload) share the
``clear``/``learn``/``raw_data`` action vocabulary and the ``send_message`` tail. Actual
transmission is delegated to the daemon's send callable (which injects the Base ID).

Payloads come from automations and templates, so anything may arrive: every value is checked
before it is used, and a malformed field is dropped on its own instead of failing the message.
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


def _to_int(value) -> int | None:
    """An EEP field value as int, or None if it is not a number (null, list, object, text).

    Accepts what HA templates produce: ints, floats (truncated, as before) and decimal strings or
    bytes such as ``"30"``. Booleans count as 1/0, matching the previous ``int(value)`` behaviour.
    """
    if isinstance(value, (bool, int)):
        return int(value)
    if isinstance(value, (float, str, bytes, bytearray)):
        try:
            return int(value)
        except (ValueError, OverflowError):  # "abc", "", "1.5", inf/nan
            return None
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
        """Handle a normal (topic-per-property) payload on ``<device>/req/<property>``."""
        found_topic = False
        for sensor in self._sensors:
            # Exact prefix match: a substring test would also hit a device whose name merely
            # contains this one's (e.g. 'x/eg/licht' for 'eg/licht') and feed it the wrong fields.
            req_prefix = sensor.name + "/req/"
            if not topic.startswith(req_prefix):
                continue
            prop = topic[len(req_prefix) :]
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
                value = _to_int(payload)
                if value is None:
                    # Expected for a malformed/non-numeric payload — DEBUG, not WARNING spam.
                    logger.debug("Cannot parse int value for %s: %s", topic, payload)
                    # Prevent storing an undefined value (would raise in the EnOcean library).
                    # The topic itself is a known one, so no "unexpected message" warning.
                    return found_topic
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
        """Handle a bulk JSON payload sent to the ``<device>/req`` topic."""
        sensor = next((s for s in self._sensors if mqtt_topic == s.name + "/req"), None)
        if sensor is None:
            return False

        # Work on a copy: the caller's dict is left untouched, and the fields are collected into a
        # new dict instead of being deleted while iterating (which raised and killed the daemon).
        payload = dict(mqtt_json_payload)
        send = "send" in payload
        actions: list[str] = []
        if send:
            send_value = payload.pop("send")
            if not isinstance(send_value, str):
                logger.warning(
                    "Ignoring command for %s: 'send' must be text such as \"clear\", got %r",
                    sensor.name,
                    send_value,
                )
                return True
            logger.debug("Send Payload: %s", send_value)
            actions = send_value.lower().split("+")

        # raw_data is never an EEP field; it is only used when the send actions ask for it.
        raw_data = payload.pop("raw_data", None)
        clear = False
        secure_teachin = False
        for action in actions:
            if action == "clear":
                clear = True
            elif action == "learn":
                sensor.mark_learn()
            elif action == "secure_teachin":
                secure_teachin = True
            elif action == "raw_data" and raw_data is not None:
                if isinstance(raw_data, str):
                    sensor.set_raw_data(raw_data)
                else:
                    logger.warning(
                        "Ignoring raw_data for %s: expected hex text, got %r", sensor.name, raw_data
                    )

        fields = {}
        for name, value in payload.items():
            number = _to_int(value)
            if number is None:
                logger.debug("Cannot parse int value for %s: %r", name, value)
                continue
            fields[name] = number

        # Append to the sensor's send buffer (keeps single topic/payload possible too).
        logger.debug("%s: req=%s", sensor.name, fields)
        if len(sensor.data or {}) + len(fields) > _MAX_ACCUMULATED_FIELDS:
            logger.debug(
                "field cap (%d) reached for %s; dropping bulk payload",
                _MAX_ACCUMULATED_FIELDS,
                sensor.name,
            )
        else:
            sensor.accumulate_many(fields)

        if send:
            await self.send_message(sensor, clear)
        if secure_teachin and self._secure_teach_in is not None:
            await self._secure_teach_in(sensor)
        return True

    async def send_message(self, sensor, clear):
        """Send a property-based MQTT message to EnOcean."""
        logger.debug("Trigger message to: %s", sensor.name)
        destination = utils.int_to_bytes(sensor.address)

        command = None
        command_shortcut = sensor.command
        if command_shortcut:
            # 'is None', not falsiness: a command id of 0 is a valid value, not a missing one.
            if not sensor.data or sensor.data.get(command_shortcut) is None:
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
