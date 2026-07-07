"""Publish one device's HA MQTT-discovery config set.

Resolve the entity map, add the common RSSI/DATE sensors, diff+delete obsolete retained configs on
update, build + publish each entity's discovery config, subscribe for delete detection + per-device
system messages, and upsert the device DB row. Everything that differs between EEP-based and
model-based discovery is supplied by a :class:`MappingLookup` strategy.
"""

from __future__ import annotations

import copy
import json
import logging
import time

from enocean2mqtt.protocol.utils import format_address

logger = logging.getLogger("enocean2mqtt.homeassistant.discovery")


class DiscoveryPublisher:
    def __init__(self, gateway, devmgr, ha_mapping, discovery_prefix, dev_name_in_entity, decorate):
        self._gateway = gateway
        self._devmgr = devmgr
        self._mapping = ha_mapping
        self._prefix = discovery_prefix
        self._dev_name_in_entity = dev_name_in_entity
        self._decorate = decorate

    def build_discovery(self, sensor, lookup):
        """Pure: build ``(dev_uid, [(cfgtopic, config), ...])`` for *sensor*. No I/O.

        This is the whole EEP-reading → HA-discovery-config translation; keeping it free of the
        broker lets it (and the exact configs it emits) be unit-tested without an MQTT connection.
        """
        is_virtual = str(sensor.virtual) == "1"

        device_map = lookup.resolve_entities(is_virtual)
        if device_map is None:
            logger.warning(
                "Device not yet supported: %s%s",
                lookup.label,
                " (Virtual)." if is_virtual else ". Only RSSI sensor will be available",
            )
            device_map = []

        if not is_virtual:
            device_map += copy.deepcopy(self._mapping["common"]["rssi"])
            device_map += copy.deepcopy(self._mapping["common"]["date"])

        address = format_address(sensor.address)
        try:
            sender = format_address(sensor.sender)
        except Exception:
            sender = "NONE"
        dev_uid = lookup.dev_uid(address, sender)

        configs = []
        for entity in device_map:
            # A name should be defined in the mapping; if not, generate one.
            if str(entity.get("name")).lower() in ("none", ""):
                entity["name"] = str(int(time.time()))
            cfg = entity["config"]
            lookup.apply_entity_override(entity, cfg)

            uid = "enocean_" + dev_uid + "_" + entity["name"]
            cfg["unique_id"] = uid
            cfg["name"] = (
                lookup.dev_name + "_" + entity["name"]
                if self._dev_name_in_entity
                else entity["name"]
            )
            cfg["device"] = lookup.device_block(address, sender, dev_uid)

            # Prefix the entity's own topics with the device topic base.
            for key in cfg:
                if "topic" in key:
                    if cfg[key] not in ("", None):
                        cfg[key] = lookup.topic_base + "/" + cfg[key]
                    else:
                        cfg[key] = lookup.topic_base

            self._decorate(cfg)
            configs.append((f"{entity['component']}/{uid}/config", cfg))
        return dev_uid, configs

    async def publish(self, sensor, lookup, prev_sensor_cfgtopics=None):
        prev = list(prev_sensor_cfgtopics or [])
        update = prev != []

        dev_uid, configs = self.build_discovery(sensor, lookup)
        sensor_cfgtopics = [cfgtopic for cfgtopic, _ in configs]

        # Delete previously-published entities no longer present in the mapping.
        if update:
            for cfgtopic in sensor_cfgtopics:
                if cfgtopic in prev:
                    prev.remove(cfgtopic)
            for cfgtopic in prev:
                await self._gateway.publish(f"{self._prefix}{cfgtopic}", "", retain=True)

        for cfgtopic, cfg in configs:
            await self._gateway.publish(f"{self._prefix}{cfgtopic}", json.dumps(cfg), retain=True)

        if sensor_cfgtopics:
            # Subscribe to one config topic to detect an MQTT delete, + per-device system topic.
            await self._gateway.subscribe(f"{self._prefix}{sensor_cfgtopics[0]}/#")
            await self._gateway.subscribe(lookup.topic_base + "/__system/#")

        self._devmgr.db_upsert_device(sensor, dev_uid, "cfgtopics", sensor_cfgtopics)
        logger.info(
            "Device %s (UID: %s / %s: %s) %s device database",
            lookup.topic_base,
            dev_uid,
            lookup.log_kind,
            lookup.label,
            "updated on" if update else "added to",
        )
