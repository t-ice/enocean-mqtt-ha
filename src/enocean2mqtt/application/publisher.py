"""Publish a decoded telegram to MQTT per the sensor's formatting policy.

Handles the RSSI/DATE auxiliary-topic emission, channel grouping, and json-vs-flat publishing,
through the :class:`AioMqttBus`.
"""

from __future__ import annotations

import json
import logging

from enocean2mqtt.config import as_bool

logger = logging.getLogger("enocean2mqtt.application.publisher")


class MqttPublisher:
    def __init__(self, gateway):
        self._gateway = gateway

    async def publish(self, sensor, mqtt_json):
        """Publish decoded packet content to MQTT."""
        # Work on a private copy: the aux-topic/channel handling below removes keys, and the caller
        # must not observe those mutations.
        mqtt_json = dict(mqtt_json)
        mqtt_publish_json = as_bool(sensor.get("publish_json"))
        mqtt_publish_rssi = as_bool(sensor.get("publish_rssi"))
        retain = as_bool(sensor.get("persistent"))

        # Is grouping enabled on this sensor?
        channel_id = sensor.get("channel")
        channel_id = channel_id.split("/") if channel_id not in (None, "") else []

        # Auxiliary data: RSSI
        aux_data = {}
        if mqtt_publish_rssi:
            if mqtt_publish_json:
                # keep _RSSI_ out of groups
                if channel_id:
                    aux_data.update({"_RSSI_": mqtt_json["_RSSI_"]})
            else:
                await self._gateway.publish(
                    sensor["name"] + "/_RSSI_", mqtt_json["_RSSI_"], retain=retain
                )
        if channel_id or not mqtt_publish_json or not mqtt_publish_rssi:
            del mqtt_json["_RSSI_"]

        # Auxiliary data: _DATE_
        if as_bool(sensor.get("publish_date")):
            if channel_id:
                if mqtt_publish_json:
                    aux_data.update({"_DATE_": mqtt_json["_DATE_"]})
                else:
                    await self._gateway.publish(
                        sensor["name"] + "/_DATE_", mqtt_json["_DATE_"], retain=retain
                    )
        else:
            del mqtt_json["_DATE_"]

        # Publish auxiliary data
        if aux_data:
            await self._gateway.publish(sensor["name"], json.dumps(aux_data), retain=retain)

        # Determine MQTT topic (append channel groups)
        topic = sensor["name"]
        for cur_id in channel_id:
            if mqtt_json.get(cur_id) not in (None, ""):
                topic += f"/{cur_id}{mqtt_json[cur_id]}"
                del mqtt_json[cur_id]

        value = json.dumps(mqtt_json)
        logger.debug("%s: Sent MQTT: %s", topic, value)

        if mqtt_publish_json:
            await self._gateway.publish(topic, value, retain=retain)
        else:
            for prop_name, value in mqtt_json.items():
                await self._gateway.publish(f"{topic}/{prop_name}", value, retain=retain)
