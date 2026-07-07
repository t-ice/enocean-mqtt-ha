"""Device manager for the Home Assistant overlay.

Backed by the stdlib ``sqlite3`` (WAL, atomic writes) instead of TinyDB — the old JSON store
did whole-file rewrites and could be left unreadable by a crash mid-write, which then prevented
the daemon from starting. Each device is stored as a JSON document (the collection is tiny, so
the field/list queries are simple in-memory scans, preserving TinyDB's document semantics).

On first start, if the ``.sqlite`` store is still empty it transparently imports a legacy TinyDB
``.json`` at the configured ``db_file`` path, so cover positions and MQTT-discovery bookkeeping
survive the upgrade. A corrupt legacy file is backed up and skipped rather than crashing the daemon.
"""

import contextlib
import json
import logging
import os
import sqlite3
import threading
import time

logger = logging.getLogger("enocean2mqtt.adapters.store")


class SqliteDeviceStore:
    """Device Manager class, providing database methods (sqlite-backed)."""

    def __init__(self, config):
        db_file = config.get("db_file")
        if not db_file:
            db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "device_db.json")

        # Derive the sqlite path from the configured (historically .json) db_file.
        if db_file.endswith(".json"):
            sqlite_path = db_file[: -len(".json")] + ".sqlite"
            legacy_json = db_file
        else:
            sqlite_path = db_file if db_file.endswith((".sqlite", ".db")) else db_file + ".sqlite"
            legacy_json = None

        self._path = sqlite_path
        # The DB is touched from both the main (EnOcean) thread and paho's network thread
        # (discovery in _on_connect, deletes in _on_mqtt_message). sqlite forbids sharing a
        # connection across threads, so allow it (check_same_thread=False) and serialize all
        # access with a lock. autocommit + WAL keeps each write durable and atomic.
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(sqlite_path, isolation_level=None, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS devices ("
            "  uid TEXT PRIMARY KEY, address INTEGER, name TEXT, doc TEXT NOT NULL)"
        )

        # One-time migration from the legacy TinyDB json.
        if legacy_json and os.path.isfile(legacy_json) and self._is_empty():
            self._migrate_from_tinydb(legacy_json)

        self.db_add_uid()
        logger.info("Device database %s correctly read/created", sqlite_path)

    # --- internals (all DB access serialized via self._lock) -------------------------------
    def _is_empty(self):
        with self._lock:
            return self._conn.execute("SELECT COUNT(*) FROM devices").fetchone()[0] == 0

    def _all(self):
        with self._lock:
            return [json.loads(r[0]) for r in self._conn.execute("SELECT doc FROM devices")]

    def _write(self, doc):
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO devices(uid, address, name, doc) VALUES (?,?,?,?)",
                (doc.get("uid"), doc.get("address"), doc.get("name"), json.dumps(doc)),
            )

    def _delete_uid(self, uid):
        with self._lock:
            self._conn.execute("DELETE FROM devices WHERE uid=?", (uid,))

    @staticmethod
    def _matches(doc, field_name, field):
        stored = doc.get(field_name)
        if isinstance(field, list):
            return all(f in (stored or []) for f in field)
        # A scalar query against a stored list means membership. This is what the MQTT-delete
        # cleanup path needs (remove the device whose 'cfgtopics' contains a given topic); the
        # old TinyDB `==` never matched a scalar against a list, so that cleanup silently no-op'd.
        if isinstance(stored, list):
            return field in stored
        return stored == field

    def _migrate_from_tinydb(self, legacy_json):
        try:
            with open(legacy_json, encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            backup = f"{legacy_json}.corrupt.{int(time.time())}"
            logger.warning(
                "Legacy DB %s unreadable (%s); backing up to %s and starting fresh",
                legacy_json,
                exc,
                backup,
            )
            with contextlib.suppress(OSError):
                os.rename(legacy_json, backup)
            return
        # TinyDB layout: {"_default": {"1": {..device..}, ...}} (or a bare list/dict fallback).
        tables = data.values() if isinstance(data, dict) else [data]
        count = 0
        for table in tables:
            rows = table.values() if isinstance(table, dict) else table
            for doc in rows:
                if isinstance(doc, dict) and doc.get("uid"):
                    self._write(doc)
                    count += 1
        logger.info("Migrated %d device(s) from legacy TinyDB store %s", count, legacy_json)

    # --- public API (preserves the previous TinyDB-backed behaviour) -----------------------
    def db_add_uid(self):
        """Update old databases without UID"""
        for device in self._all():
            if not device.get("uid"):
                eep = format((device["rorg"] << 16) + (device["func"] << 8) + device["type"], "06X")
                device["uid"] = eep + "_" + format(device["address"], "08X") + "_NONE"
                self._write(device)

    def db_search_device_by_field(self, field_name, field):
        """Search device in the database using a device field"""
        return any(self._matches(d, field_name, field) for d in self._all())

    def db_get_device_by_field(self, field_name, field):
        """Get device from the database using a device field"""
        return next((d for d in self._all() if self._matches(d, field_name, field)), None)

    # Convenience wrappers over the generic field lookups (address/name are always scalars).
    def db_search_device_by_address(self, address):
        """Search device in the database using the device address"""
        return self.db_search_device_by_field("address", address)

    def db_get_device_by_address(self, address):
        """Get device from the database using the device address"""
        return self.db_get_device_by_field("address", address)

    def db_get_device_by_name(self, name):
        """Get device from the database using the device name"""
        return self.db_get_device_by_field("name", name)

    def db_get_devices(self):
        """Get all devices from the database"""
        return self._all()

    def db_list_from_fields(self, field):
        """Get a list of field values for all devices in the database"""
        return [d[field] for d in self._all()]

    def get_position(self, address):
        """Get the persisted cover position for a device (None if unknown)"""
        device = self.db_get_device_by_address(address)
        return device.get("position") if device else None

    def set_position(self, address, position):
        """Persist the cover position for a device (keyed by EnOcean address)"""
        for device in self._all():
            if device.get("address") == address:
                device["position"] = position
                self._write(device)

    def get_rlc(self, address):
        """Persisted secure rolling codes ``(rlc, rlc_snd)`` for a device (None each if unset)."""
        device = self.db_get_device_by_address(address)
        if not device:
            return (None, None)
        return device.get("rlc"), device.get("rlc_snd")

    def set_rlc(self, address, rlc=None, rlc_snd=None):
        """Persist the secure rolling code(s) for a device (keyed by EnOcean address)."""
        for device in self._all():
            if device.get("address") == address:
                if rlc is not None:
                    device["rlc"] = rlc
                if rlc_snd is not None:
                    device["rlc_snd"] = rlc_snd
                self._write(device)

    def db_add_device(self, sensor, uid, attr_name=None, attr=None):
        """Add new device to the database"""
        if not self.db_search_device_by_address(sensor["address"]):
            sensor_db = {
                "uid": uid,
                "address": sensor["address"],
                "name": sensor["name"],
                "rorg": sensor["rorg"],
                "func": sensor["func"],
                "type": sensor["type"],
            }
            if attr is not None:
                sensor_db[attr_name] = attr
            self._write(sensor_db)
            return True
        return False

    def db_update_device(self, sensor, uid, attr_name=None, attr=None):
        """Update device on the database"""
        existing = self.db_get_device_by_field("uid", sensor["uid"])
        if existing:
            existing["name"] = sensor["name"]
            if attr is not None:
                existing[attr_name] = attr
            existing["uid"] = uid
            self._write(existing)
            return True
        return False

    def db_upsert_device(self, sensor, uid, attr_name=None, attr=None):
        """Update or add device to the database"""
        sensor_db = {"uid": uid}
        if not sensor.get("model"):
            sensor_db["address"] = sensor["address"]
            sensor_db["name"] = sensor["name"]
            sensor_db["rorg"] = sensor["rorg"]
            sensor_db["func"] = sensor["func"]
            sensor_db["type"] = sensor["type"]
        else:
            sensor_db["address"] = sensor["address"]
            sensor_db["name"] = sensor["name"][:-3]
            sensor_db["model"] = sensor["model"]
        if attr is not None:
            sensor_db[attr_name] = attr
        self._write(sensor_db)

    def db_remove_device_by_address(self, address):
        """Remove device from the database using device address"""
        removed = False
        for d in self._all():
            if d.get("address") == address:
                self._delete_uid(d.get("uid"))
                removed = True
        return removed

    def db_remove_device_by_field(self, field_name, field):
        """Remove device from the database using a device field"""
        sensor = self.db_get_device_by_field(field_name, field)
        if sensor:
            self._delete_uid(sensor.get("uid"))
            logger.debug(
                "Delete request for sensor %s (UID %s): DONE", sensor.get("name"), sensor.get("uid")
            )
            return True
        return False
