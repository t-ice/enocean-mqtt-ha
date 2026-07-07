"""Home Assistant overlay for the EnOcean↔MQTT daemon — by composition, not inheritance.

``HomeAssistantBridge`` *has-a* :class:`EnoceanDaemon` and registers itself as the daemon's
``overlay``. The daemon invokes four lifecycle hooks — ``before_connect``, ``after_connect``,
``intercept_inbound`` and ``before_publish`` — into which the bridge folds HA MQTT-discovery, the
LEARN/teach-in system controls, and the cover-position persistence. The bridge talks to the daemon
only through its public service surface (``publish``/``subscribe``/``sensors``/``conf``/``bus``/
``bridge_state_topic``/``base_id_ready``/``teach_in``), so there is no fragile base class and no
reaching into daemon internals.
"""

import asyncio
import contextlib
import copy
import json
import logging
from importlib.metadata import PackageNotFoundError, version

import enocean2mqtt.protocol.utils
from enocean2mqtt.adapters.store.sqlite_store import SqliteDeviceStore
from enocean2mqtt.application.daemon import _BASE_ID_TIMEOUT, EnoceanDaemon
from enocean2mqtt.config import as_bool
from enocean2mqtt.devices import append_device_to_yaml
from enocean2mqtt.domain.config import Config
from enocean2mqtt.domain.sensor import Sensor
from enocean2mqtt.homeassistant.cover import update_cover_position
from enocean2mqtt.homeassistant.discovery.mapping_lookup import EepMappingLookup, ModelMappingLookup
from enocean2mqtt.homeassistant.discovery.publisher import DiscoveryPublisher
from enocean2mqtt.homeassistant.mapping import MAPPING
from enocean2mqtt.homeassistant.sensor_expander import SensorExpander

logger = logging.getLogger("enocean2mqtt.homeassistant.ha_bridge")

try:
    _SW_VERSION = version("enocean-mqtt-ha")
except PackageNotFoundError:  # running from a source checkout without install
    _SW_VERSION = "0.0.0"

# HA MQTT-discovery `origin` block, attached to every discovery payload.
_ORIGIN = {
    "name": "EnOcean MQTT for Home Assistant",
    "sw_version": _SW_VERSION,
    "support_url": "https://github.com/t-ice/enocean-mqtt-ha",
}

# Fields of the retained bridge/stats JSON, surfaced as HA diagnostic sensors on the bridge device.
# (field, name, extra discovery keys). Counters use total_increasing (they reset to 0 on restart).
_BRIDGE_STATS = (
    (
        "uptime_s",
        "Uptime",
        {"device_class": "duration", "unit_of_measurement": "s", "state_class": "measurement"},
    ),
    ("telegrams_total", "Telegrams received", {"state_class": "total_increasing"}),
    (
        "telegrams_per_min",
        "Telegram rate",
        {"unit_of_measurement": "1/min", "state_class": "measurement"},
    ),
    ("unknown_senders", "Unknown-sender telegrams", {"state_class": "total_increasing"}),
    ("mqtt_reconnects", "MQTT reconnects", {"state_class": "total_increasing"}),
    ("transceiver_reconnects", "Transceiver reconnects", {"state_class": "total_increasing"}),
    ("base_id", "Transceiver Base ID", {"icon": "mdi:identifier"}),
    ("stick_app_version", "Transceiver app version", {"icon": "mdi:chip"}),
    ("stick_api_version", "Transceiver API version", {"icon": "mdi:chip"}),
    ("chip_id", "Transceiver chip ID", {"icon": "mdi:chip"}),
    ("repeater_level", "Repeater level", {"icon": "mdi:repeat"}),
    (
        "duty_cycle_available",
        "TX duty-cycle available",
        {"unit_of_measurement": "%", "state_class": "measurement", "icon": "mdi:radio-tower"},
    ),
    ("transmit_failures", "Transmit failures", {"state_class": "total_increasing"}),
)


class HomeAssistantBridge:
    """Composes an EnoceanDaemon and layers Home Assistant discovery / controls on top of it."""

    # Safety: teach-in auto-disables after this many seconds, so a forgotten-on learn mode does not
    # keep mass-accepting stray telegrams.
    _LEARN_TIMEOUT_S = 300

    # Eltako shutter/blind models whose telegrams only carry the relative running time of the last
    # movement; the bridge accumulates + persists an absolute position (see _update_cover_position).
    _COVER_MODELS = ("fsb14", "fsb61", "fj62")

    def __init__(self, config, sensors):
        config = Config.from_mapping(config)
        # The HA device/entity mapping is code-defined (mapping.MAPPING); deep-copied so the bridge
        # may annotate it at runtime without mutating the shared module constant.
        self._ha_mapping = copy.deepcopy(MAPPING)

        # Expand model-based sensors into per-RORG entity sensors + overlay EEP device_config.
        sensors = SensorExpander(self._ha_mapping).expand(sensors)

        self._devmgr = SqliteDeviceStore(config)
        self._dev_name_in_entity = config.ha_dev_name_in_entity
        self._mqtt_discovery_prefix = config.mqtt_discovery_prefix
        if self._mqtt_discovery_prefix[-1] != "/":
            self._mqtt_discovery_prefix += "/"

        self._first_mqtt_connect = True
        self._system_status_topic: dict = {}
        self._learn_timer = None

        # Compose the base daemon and register this bridge as its lifecycle overlay.
        self._daemon = EnoceanDaemon(config, sensors)
        self._daemon.overlay = self
        # Disable Teach-in on startup (the LEARN button re-enables it).
        self._daemon.teach_in = False
        logger.info("Auto Teach-in is %s", "enabled" if self._daemon.teach_in else "disabled")

        # HA discovery publisher — the daemon is its message bus (publish/subscribe surface).
        self._discovery = DiscoveryPublisher(
            self._daemon,
            self._devmgr,
            self._ha_mapping,
            self._mqtt_discovery_prefix,
            self._dev_name_in_entity,
            self._decorate_discovery,
        )

        # Secure telegrams: persist advanced rolling codes durably, and restore them at startup so a
        # device isn't rejected (or window-scanned) after a restart.
        self._daemon.on_secure_state_change = self._persist_secure_state
        self._load_secure_rlc()

    def run(self):
        """Run the composed daemon's asyncio loop (blocking)."""
        self._daemon.run()

    # --- facade over the composed daemon (used by this bridge and its tests) ---------------------
    @property
    def sensors(self):
        return self._daemon.sensors

    @property
    def conf(self):
        return self._daemon.conf

    @property
    def enocean_sender(self):
        return self._daemon.enocean_sender

    @property
    def teach_in(self) -> bool:
        return self._daemon.teach_in

    @teach_in.setter
    def teach_in(self, value: bool) -> None:
        self._daemon.teach_in = value

    @property
    def _client(self):
        return self._daemon._client

    @_client.setter
    def _client(self, value):
        self._daemon._client = value

    @property
    def _base_id_ready(self):
        return self._daemon.base_id_ready

    # =============================================================================================
    # Daemon lifecycle hooks (invoked by EnoceanDaemon.overlay)
    # =============================================================================================
    async def before_connect(self):
        """Discovery needs the transceiver Base ID; wait for it (bounded) before announcing."""
        if not self._daemon.base_id_ready.is_set():
            try:
                await asyncio.wait_for(self._daemon.base_id_ready.wait(), timeout=_BASE_ID_TIMEOUT)
            except TimeoutError:
                logger.warning("Base ID not received within %ss; proceeding", _BASE_ID_TIMEOUT)

    async def after_connect(self):
        """On the first broker connect only: run discovery + publish the LEARN button and covers."""
        if not self._first_mqtt_connect:
            return
        await self._sync_sensor_discovery()
        if self._daemon.enocean_sender is None:
            # The transceiver never reported a Base ID (see before_connect's timeout). The LEARN
            # button and bridge-stats entities are keyed on it, so skip them rather than crash.
            # This usually means the configured 'device' isn't the EnOcean stick (e.g. a host
            # console UART like /dev/ttyS0) or the port/endpoint is wrong.
            logger.error(
                "Transceiver reported no Base ID — skipping the LEARN button and bridge-stats "
                "entities. Check the 'device' path (is it really the EnOcean stick?) or use 'tcp'."
            )
        else:
            # Add the LEARN button + publish its status (must follow the button's discovery).
            await self._mqtt_discovery_system("learn")
            await self._daemon.publish(
                self._system_status_topic["learn"],
                "ON" if self._daemon.teach_in else "OFF",
                retain=True,
            )
            await self._mqtt_discovery_stats()
        await self._publish_cover_shut_times()
        self._first_mqtt_connect = False

    async def intercept_inbound(self, topic, payload) -> bool:
        """Claim system + discovery-delete topics; return True if handled (base skips dispatch)."""
        if "/__system" in topic:
            await self._handle_system_msg(topic, payload)
            return True
        if topic.startswith(self._mqtt_discovery_prefix) and topic.endswith("/config"):
            # A retained discovery config was cleared (empty payload) -> a delete request.
            if len(payload) == 0:
                await self._handle_system_msg(topic, payload, delete=True)
            return True  # discovery-config traffic is ours either way
        return False

    def before_publish(self, sensor, mqtt_json):
        """For shutter/blind models, derive + persist an absolute cover position (POS)."""
        if sensor.model in self._COVER_MODELS:
            self._update_cover_position(sensor, mqtt_json)

    # =============================================================================================
    # DISCOVERY
    # =============================================================================================
    def _discovery_identity(self, sensor):
        """Return ``(dev_uid, db_name, discover_fn)`` for a configured sensor.

        EEP-based devices are keyed by their EEP code; model-based devices by manufacturer + model.
        Both append the (hex) address and sender to form a unique id.
        """
        fmt = enocean2mqtt.protocol.utils.format_address
        try:
            sender = fmt(sensor.sender)
        except (TypeError, ValueError):
            # A senderless sensor (no 'sender' configured) has no address to format — "NONE" is the
            # intended UID component for it. Narrow catch so unexpected errors still surface.
            sender = "NONE"
        address = fmt(sensor.address)
        if not sensor.model:
            eep = format((sensor.rorg << 16) + (sensor.func << 8) + sensor.type, "06X")
            return f"{eep}_{address}_{sender}", sensor.name, self._mqtt_discovery_eep
        dev_uid = f"{sensor.manufacturer}_{sensor.model}_{address}_{sender}"
        return dev_uid, sensor.name[:-3], self._mqtt_discovery_model  # name[:-3] strips "/RORG"

    async def _prune_deleted_devices(self, known_uids):
        """Remove discovery for devices no longer listed in the config (their retained topics)."""
        logger.debug("List of remaining UIDS: %s", str(known_uids))
        for dev_uid in known_uids:
            sensor_db = self._devmgr.db_get_device_by_field("uid", dev_uid)
            if sensor_db:
                for cfgtopic in sensor_db.get("cfgtopics", []):
                    await self._daemon.publish(
                        f"{self._mqtt_discovery_prefix}{cfgtopic}", "", retain=True
                    )
            self._devmgr.db_remove_device_by_field("uid", dev_uid)

    async def _sync_sensor_discovery(self):
        """Discover/update every configured sensor, then prune devices no longer in the config."""
        known_uids = self._devmgr.db_list_from_fields("uid")
        for sensor in self._daemon.sensors:
            if sensor.ignore:
                continue
            dev_uid, db_name, discover = self._discovery_identity(sensor)
            sensor_db = self._devmgr.db_get_device_by_field("name", db_name)
            cfgtopics = sensor_db.get("cfgtopics", None) if sensor_db else None
            await discover(sensor, cfgtopics)
            with contextlib.suppress(ValueError):
                known_uids.remove(dev_uid)
        await self._prune_deleted_devices(known_uids)

    async def _publish_cover_shut_times(self):
        """Publish each cover's configured run time as a retained attribute (single source of truth
        for set_position_template), so a separate HA number entity is unnecessary."""
        for sensor in self._daemon.sensors:
            if (
                sensor.model in self._COVER_MODELS
                and sensor.shut_time is not None
                and sensor.rorg == 0xA5
            ):
                await self._daemon.publish(
                    sensor.name[:-3] + "/shut_time", sensor.shut_time, retain=True
                )

    def _decorate_discovery(self, cfg):
        """Add availability (LWT) + origin to a discovery config.

        Called AFTER the per-entity topic-prefixing loop so ``availability_topic`` (which contains
        'topic') keeps the global bridge state topic instead of being prefixed.
        """
        cfg["availability_topic"] = self._daemon.bridge_state_topic
        cfg["payload_available"] = "online"
        cfg["payload_not_available"] = "offline"
        cfg["origin"] = _ORIGIN
        return cfg

    async def _mqtt_discovery_system(self, attr):
        """Publish MQTT discovery system entities configuration to Home Assistant."""
        prefix = self._daemon.conf.mqtt_prefix
        device_map = copy.deepcopy(self._ha_mapping["system"][attr])
        for entity in device_map:
            cfg = entity["config"]
            # Base ID is known here — after_connect skips these system entities when it's absent.
            sender = enocean2mqtt.protocol.utils.combine_hex(self._daemon.enocean_sender)
            sender_hex = enocean2mqtt.protocol.utils.format_address(sender)
            uid = "enocean2mqtt_" + attr + "_" + sender_hex
            cfg["unique_id"] = uid
            cfg["name"] = entity["name"]
            cfg["device"] = {
                "name": "ENOCEAN2MQTT",
                "identifiers": sender_hex,
                "model": "Virtual @" + sender_hex,
                "manufacturer": "EnOcean MQTT for Home Assistant",
                "configuration_url": "https://github.com/t-ice/enocean-mqtt-ha",
            }
            cfgtopic = f"{self._mqtt_discovery_prefix}{entity['component']}/{uid}/config"
            # Append defined entity's topics to the device topic.
            for key in cfg:
                if "topic" in key:
                    if cfg[key] not in ("", None):
                        cfg[key] = prefix + "__system/" + cfg[key]
                    else:
                        cfg[key] = prefix + "__system"
            self._decorate_discovery(cfg)
            await self._daemon.publish(cfgtopic, json.dumps(cfg), retain=True)
        # listen to HA learn requests
        await self._daemon.subscribe(prefix + "__system/" + attr + "/req/#")
        self._system_status_topic[attr] = prefix + "__system/" + attr

    async def _mqtt_discovery_stats(self):
        """Publish bridge/stats fields as HA diagnostic sensors on the bridge device."""
        if self._daemon.enocean_sender is None:
            logger.debug("Base ID unknown; skipping bridge/stats diagnostic discovery")
            return
        stats_topic = self._daemon.conf.mqtt_prefix + "bridge/stats"
        sender = enocean2mqtt.protocol.utils.combine_hex(self._daemon.enocean_sender)
        sender_hex = enocean2mqtt.protocol.utils.format_address(sender)
        device = {
            "name": "ENOCEAN2MQTT",
            "identifiers": sender_hex,
            "model": "Virtual @" + sender_hex,
            "manufacturer": "EnOcean MQTT for Home Assistant",
            "configuration_url": "https://github.com/t-ice/enocean-mqtt-ha",
        }
        for field, name, extra in _BRIDGE_STATS:
            uid = f"enocean2mqtt_stat_{field}_{sender_hex}"
            cfg = {
                "unique_id": uid,
                "name": name,
                "state_topic": stats_topic,
                "value_template": "{{ value_json." + field + " }}",
                "entity_category": "diagnostic",
                "device": device,
                **extra,
            }
            self._decorate_discovery(cfg)
            cfgtopic = f"{self._mqtt_discovery_prefix}sensor/{uid}/config"
            await self._daemon.publish(cfgtopic, json.dumps(cfg), retain=True)

    async def _mqtt_discovery_eep(self, sensor, prev_sensor_cfgtopics=None):
        """Publish EEP-based MQTT discovery (delegates to DiscoveryPublisher + EEP strategy)."""
        lookup = EepMappingLookup(sensor, self._ha_mapping, self._daemon.conf.mqtt_prefix)
        await self._discovery.publish(sensor, lookup, prev_sensor_cfgtopics)

    async def _mqtt_discovery_model(self, sensor, prev_sensor_cfgtopics=None):
        """Publish model-based MQTT discovery (delegates to DiscoveryPublisher + model strategy)."""
        lookup = ModelMappingLookup(sensor, self._ha_mapping, self._daemon.conf.mqtt_prefix)
        await self._discovery.publish(sensor, lookup, prev_sensor_cfgtopics)

    # =============================================================================================
    # SYSTEM (LEARN / teach-in)
    # =============================================================================================
    async def _handle_system_msg(self, topic, payload, delete=False):
        """Handle system-related MQTT messages."""
        if delete:
            # A delete request on an MQTT discovery configuration topic.
            cfgtopic = topic.split(self._mqtt_discovery_prefix)[1]
            self._devmgr.db_remove_device_by_field("cfgtopics", cfgtopic)
        else:
            [target_name, prop] = [topic.split("/__system")[i] for i in (0, -1)]
            # Global system request: the learn (teach-in) toggle.
            if target_name == self._daemon.conf.mqtt_prefix[:-1] and prop == "/learn/req":
                await self._set_teach_in(payload.decode("UTF-8") == "ON")

    async def _set_teach_in(self, enabled: bool):
        """Enable/disable teach-in, publish the LEARN status, and (dis)arm the auto-off timer."""
        self._daemon.teach_in = enabled
        await self._daemon.publish(
            self._system_status_topic["learn"], "ON" if enabled else "OFF", retain=True
        )
        if self._learn_timer is not None:
            self._learn_timer.cancel()
            self._learn_timer = None
        if enabled:
            logger.info("Teach-in enabled (auto-off in %ds)", self._LEARN_TIMEOUT_S)
            self._learn_timer = asyncio.create_task(self._auto_disable_learn())
        else:
            logger.info("Teach-in disabled")

    async def _auto_disable_learn(self):
        try:
            await asyncio.sleep(self._LEARN_TIMEOUT_S)
        except asyncio.CancelledError:
            return
        logger.warning("Teach-in auto-disabled after %ds", self._LEARN_TIMEOUT_S)
        await self._set_teach_in(False)

    async def on_teach_in(self, packet):
        """Auto-provision a newly taught-in device while learn mode is on (daemon hook).

        A UTE teach-in carries a full EEP (rorg/func/type); we synthesize a Sensor, add it to the
        sensor list so its telegrams decode immediately, publish HA discovery, and append it to the
        user's ``devices.yaml`` so it survives a restart. Non-EEP teach-ins (RPS/1BS carry no
        func/type) are skipped — there's no decodable profile to derive. Idempotent by address.
        """
        if not self._daemon.teach_in:
            return
        rorg = getattr(packet, "rorg_of_eep", None)
        func = getattr(packet, "rorg_func", None)
        type_ = getattr(packet, "rorg_type", None)
        if rorg is None or func is None or type_ is None:
            logger.info("Teach-in without a usable EEP; not auto-provisioning")
            return
        address = packet.sender_int
        if any(s.address == address for s in self._daemon.sensors):
            logger.debug("Teach-in from already-known device 0x%08X; ignoring", address)
            return

        name = (
            self._daemon.conf.mqtt_prefix
            + "auto_"
            + enocean2mqtt.protocol.utils.format_address(address)
        )
        entry = {"name": name, "address": address, "rorg": rorg, "func": func, "type": type_}
        # expand() applies the forced HA flags + overlays the EEP's device_config (for actuators).
        [new_sensor] = SensorExpander(self._ha_mapping).expand([Sensor.from_dict(dict(entry))])
        self._daemon.sensors.append(new_sensor)
        logger.info(
            "Auto-provisioned EnOcean device %s (EEP %02X-%02X-%02X)", name, rorg, func, type_
        )

        # Publish HA discovery so the device appears immediately (EEP path; no model).
        _uid, _db_name, discover = self._discovery_identity(new_sensor)
        await discover(new_sensor, None)

        # Persist so it survives a restart, and announce it.
        self._persist_auto_device(entry)
        await self._daemon.publish(
            self._daemon.conf.mqtt_prefix + "bridge/last_provisioned", name, retain=True
        )

    async def on_secure_teach_in(self, teach_in, sender):
        """Provision/annotate a secure device from a SEC_TI teach-in (daemon hook, learn mode).

        If the device is already known (configured or UTE-taught), enable security on it; else a
        PTM (switch) teach-in provisions a fresh secure F6-02-01 device. A non-PTM key with no known
        EEP is logged for the user to attach manually (the EEP isn't in the secure teach-in).
        """
        if not self._daemon.teach_in:
            return
        address = enocean2mqtt.protocol.utils.combine_hex(sender)
        key_hex = teach_in.key.hex().upper()
        existing = next((s for s in self._daemon.sensors if s.address == address), None)
        if existing is not None:
            existing["security"] = True
            existing["key"] = key_hex
            existing["rlc"] = teach_in.rlc
            existing["slf"] = teach_in.slf
            self._persist_secure_state(existing)
            logger.info(
                "Secure key learned for %s; add security:/key: to its devices.yaml entry",
                existing.name,
            )
            return
        if not teach_in.ptm:
            logger.info(
                "Secure key learned for 0x%08X but its EEP is unknown — teach it (UTE) or add it "
                "to devices.yaml with security: + key: first",
                address,
            )
            return
        addr_hex = enocean2mqtt.protocol.utils.format_address(address)
        name = self._daemon.conf.mqtt_prefix + "secure_" + addr_hex
        entry = {
            "name": name,
            "address": address,
            "rorg": 0xF6,
            "func": 0x02,
            "type": 0x01,
            "security": True,
            "key": key_hex,
            "rlc": teach_in.rlc,
            "slf": teach_in.slf,
        }
        [new_sensor] = SensorExpander(self._ha_mapping).expand([Sensor.from_dict(dict(entry))])
        self._daemon.sensors.append(new_sensor)
        logger.info("Auto-provisioned secure device %s (F6-02-01)", name)
        _uid, _db_name, discover = self._discovery_identity(new_sensor)
        await discover(new_sensor, None)
        self._persist_secure_device(entry)
        await self._daemon.publish(
            self._daemon.conf.mqtt_prefix + "bridge/last_provisioned", name, retain=True
        )

    def _persist_secure_state(self, sensor):
        """Durably persist a secure device's advanced rolling code(s) to the store (RX/TX hook)."""
        try:
            self._devmgr.set_rlc(sensor.address, sensor.rlc, sensor.rlc_snd)
        except Exception as err:
            # Best-effort persist, but a failure must be visible: a silently-dropped write would
            # re-accept an already-seen rolling code after a restart (replay window).
            logger.error("Failed to persist rolling code for %s: %s", sensor.address, err)

    def _load_secure_rlc(self):
        """Restore persisted rolling codes into secure sensors at startup."""
        for sensor in self._daemon.sensors:
            if not as_bool(sensor.security):
                continue
            rlc, rlc_snd = self._devmgr.get_rlc(sensor.address)
            if rlc is not None:
                sensor["rlc"] = rlc
            if rlc_snd is not None:
                sensor["rlc_snd"] = rlc_snd

    def _persist_secure_device(self, entry):
        """Append a secure auto-provisioned device (with its key) to the user's devices.yaml."""
        device_file = self._daemon.conf.get("device_file")
        if not device_file:
            return
        prefix = self._daemon.conf.mqtt_prefix
        bare = entry["name"][len(prefix) :] if entry["name"].startswith(prefix) else entry["name"]
        try:
            append_device_to_yaml(
                device_file,
                {
                    "name": bare,
                    "address": hex(entry["address"]),
                    "eep": f"{entry['rorg']:02X}-{entry['func']:02X}-{entry['type']:02X}",
                    "security": True,
                    "key": entry["key"],
                    "rlc": entry["rlc"],
                    "slf": entry["slf"],
                },
            )
        except OSError as exc:
            logger.warning("Could not persist secure device to devices.yaml: %s", exc)

    def _persist_auto_device(self, entry):
        """Append the auto-provisioned device to the user's devices.yaml (best-effort).

        Uses ruamel round-trip so the user's comments/formatting are preserved. The stored name is
        *bare* (the loader re-adds the mqtt_prefix on the next start).
        """
        device_file = self._daemon.conf.get("device_file")
        if not device_file:
            logger.debug("No device_file path known; auto-provisioned device is runtime-only")
            return
        prefix = self._daemon.conf.mqtt_prefix
        bare_name = entry["name"]
        if bare_name.startswith(prefix):
            bare_name = bare_name[len(prefix) :]
        try:
            append_device_to_yaml(
                device_file,
                {
                    "name": bare_name,
                    "address": hex(entry["address"]),
                    "eep": f"{entry['rorg']:02X}-{entry['func']:02X}-{entry['type']:02X}",
                },
            )
        except OSError as exc:
            logger.warning("Could not persist auto-provisioned device to devices.yaml: %s", exc)

    # =============================================================================================
    # ENOCEAN TO MQTT (cover position)
    # =============================================================================================
    def _update_cover_position(self, sensor, mqtt_json):
        """Maintain an absolute cover position for FSB-type actuators and persist it.

        Thin DB wrapper around the pure :func:`cover.update_cover_position`.
        """
        address = sensor.address
        pos = update_cover_position(
            self._devmgr.get_position(address),
            mqtt_json.get("_RAW_DATA_"),
            mqtt_json,
            sensor.shut_time,
        )
        if pos is None:
            return
        mqtt_json["POS"] = pos
        self._devmgr.set_position(address, pos)
