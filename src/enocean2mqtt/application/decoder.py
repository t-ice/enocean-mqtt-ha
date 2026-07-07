"""Decode a received EnOcean telegram into an MQTT payload dict.

Decoding is done by the code-defined engine (``profiles.engine`` over ``PROFILES``) via
``packet.parse_eep``; the received data bits satisfy each case's ``<condition>`` predicates, so
command/direction selection happens automatically. The published representation is the scaled
``value`` for numeric fields, else the ``raw_value`` (so enum wording never reaches MQTT). Field
keys are the official EEP shortcuts; the HA mapping references them directly (bracket notation for
shortcuts that aren't valid identifiers, e.g. ``value_json['A/PM']``).
"""

from __future__ import annotations

import logging
import numbers

import enocean2mqtt.protocol.utils

logger = logging.getLogger("enocean2mqtt.application.decoder")

# Telegram metadata the engine exposes as a field but which is not a reading (the 4BS learn bit);
# teach-in is handled separately, so it is not published to MQTT.
_META_SHORTCUTS = frozenset({"LRN", "LRNB"})


class PacketDecoder:
    @staticmethod
    def decode(packet, sensor) -> dict | None:
        """Decode the telegram into a fresh MQTT payload dict, or None if no property was decoded.

        Returns the decoded fields plus ``_RAW_DATA_``. The caller owns the returned dict and merges
        in transport metadata (``_RSSI_``/``_DATE_``) — the decoder no longer mutates a dict passed
        in by the caller.
        """
        # The mapping's device_config uses '' as "unset"; an empty direction must NOT be passed as a
        # real filter (it would select no case and drop the telegram). Normalise falsy -> None.
        direction = sensor.direction or None
        properties = packet.parse_eep(sensor.func, sensor.type, direction)

        mqtt_json: dict = {}
        for prop_name in properties:
            if prop_name in _META_SHORTCUTS:
                continue
            decoded_field = packet.parsed[prop_name]
            logger.debug(
                "%s: %s (%s)=%s %s",
                sensor.name,
                prop_name,
                decoded_field["description"],
                decoded_field["value"],
                decoded_field["unit"],
            )
            mqtt_json[prop_name] = PacketDecoder._publish_value(decoded_field)

        if not mqtt_json:
            return None
        PacketDecoder._add_raw_data(packet, mqtt_json)
        return mqtt_json

    @staticmethod
    def _publish_value(decoded_field):
        """The MQTT-published representation: the scaled value, or the raw value for enums."""
        value = decoded_field["value"]
        return value if isinstance(value, numbers.Number) else decoded_field["raw_value"]

    @staticmethod
    def _add_raw_data(packet, mqtt_json):
        """Publish the raw payload bytes alongside the decoded properties."""
        raw_data = packet.data[1 : len(packet.data) - 1 - 4]
        raw_data.append(packet.data[-1])
        mqtt_json["_RAW_DATA_"] = enocean2mqtt.protocol.utils.to_hex_string(raw_data)
