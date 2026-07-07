"""Tests for the sqlite-backed SqliteDeviceStore (incl. legacy migration + corruption recovery)."""

import json

from enocean2mqtt.adapters.store.sqlite_store import SqliteDeviceStore


def mgr(tmp_path, name="enocean2mqtt_db.json"):
    return SqliteDeviceStore({"db_file": str(tmp_path / name)})


def test_upsert_get_and_position(tmp_path):
    dm = mgr(tmp_path)
    sensor = {
        "address": 0x059ED79A,
        "name": "enocean2mqtt/Wetter",
        "rorg": 0xA5,
        "func": 0x13,
        "type": 0x01,
    }
    dm.db_upsert_device(sensor, "A51301_059ED79A_NONE", "cfgtopics", ["sensor/x/config"])

    got = dm.db_get_device_by_field("uid", "A51301_059ED79A_NONE")
    assert got["name"] == "enocean2mqtt/Wetter"
    assert got["cfgtopics"] == ["sensor/x/config"]
    assert dm.db_list_from_fields("uid") == ["A51301_059ED79A_NONE"]

    # position persistence keyed by address
    assert dm.get_position(0x059ED79A) is None
    dm.set_position(0x059ED79A, 42)
    assert dm.get_position(0x059ED79A) == 42


def test_position_survives_reopen(tmp_path):
    dm = mgr(tmp_path)
    dm.db_upsert_device(
        {"address": 5, "name": "enocean2mqtt/Rollo", "rorg": 0xA5, "func": 0x3F, "type": 0x7F},
        "uid5",
    )
    dm.set_position(5, 73)
    # New manager on the same path (simulates add-on restart)
    dm2 = mgr(tmp_path)
    assert dm2.get_position(5) == 73


def test_remove_by_cfgtopics_list_contains(tmp_path):
    dm = mgr(tmp_path)
    dm.db_upsert_device(
        {"address": 1, "name": "enocean2mqtt/A", "rorg": 0xF6, "func": 0x02, "type": 0x01},
        "uidA",
        "cfgtopics",
        ["switch/a/config", "sensor/a/config"],
    )
    assert dm.db_remove_device_by_field("cfgtopics", "sensor/a/config") is True
    assert dm.db_get_device_by_field("uid", "uidA") is None


def test_migrates_legacy_tinydb(tmp_path):
    legacy = tmp_path / "enocean2mqtt_db.json"
    legacy.write_text(
        json.dumps(
            {
                "_default": {
                    "1": {
                        "uid": "u1",
                        "address": 5,
                        "name": "Rollo",
                        "position": 88,
                        "cfgtopics": ["cover/5/config"],
                    },
                }
            }
        )
    )
    dm = mgr(tmp_path)  # same .json path -> sqlite sibling, imports legacy
    assert dm.get_position(5) == 88
    assert dm.db_get_device_by_field("cfgtopics", "cover/5/config")["uid"] == "u1"


def test_cross_thread_access(tmp_path):
    """The DB is used from paho's network thread (discovery) as well as the main thread —
    sqlite forbids sharing a connection across threads unless check_same_thread=False + a lock."""
    import threading

    dm = mgr(tmp_path)
    dm.db_upsert_device(
        {"address": 5, "name": "enocean2mqtt/X", "rorg": 0xA5, "func": 0x13, "type": 0x01},
        "uidX",
        "cfgtopics",
        ["c/1"],
    )
    errors = []

    def worker():
        try:
            dm.db_list_from_fields("uid")  # read (what _on_connect does)
            dm.set_position(5, 55)  # write
            dm.db_remove_device_by_field("cfgtopics", "c/1")  # delete
        except Exception as exc:
            errors.append(exc)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert not errors, f"cross-thread DB access raised: {errors}"


def test_corrupt_legacy_is_backed_up_not_fatal(tmp_path):
    legacy = tmp_path / "enocean2mqtt_db.json"
    legacy.write_text('{"_default": {"1": {truncated…')  # invalid JSON
    dm = mgr(tmp_path)  # must not raise
    assert dm.db_get_devices() == []
    backups = list(tmp_path.glob("enocean2mqtt_db.json.corrupt.*"))
    assert backups, "corrupt legacy file should be backed up"
