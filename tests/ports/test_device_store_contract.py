"""Behavioral contract for DeviceStorePort — upgrades the structural conformance check to real
behaviour. `check_device_store_contract` is implementation-agnostic, so any DeviceStorePort (the
SQLite adapter here, or a future in-memory fake) can be validated against the same expectations."""

from enocean2mqtt.adapters.store.sqlite_store import SqliteDeviceStore
from enocean2mqtt.domain.sensor import Sensor


def check_device_store_contract(store):
    """Exercise the DeviceStorePort behaviour any implementation must satisfy."""
    sensor = Sensor.from_dict(
        {"name": "e2m/x", "address": 0x05010203, "rorg": 0xA5, "func": 0x02, "type": 0x05}
    )

    # upsert then look up by uid and by name; the extra (attr_name, attr) is stored too.
    store.db_upsert_device(sensor, "UID1", "cfgtopics", ["sensor/UID1/config"])
    rec = store.db_get_device_by_field("uid", "UID1")
    assert rec is not None and rec["uid"] == "UID1" and rec["name"] == "e2m/x"
    assert rec["cfgtopics"] == ["sensor/UID1/config"]
    assert store.db_get_device_by_name("e2m/x")["uid"] == "UID1"
    assert "UID1" in store.db_list_from_fields("uid")

    # position round-trips (keyed by EnOcean address); unknown → None.
    assert store.get_position(0x05010203) is None
    store.set_position(0x05010203, 42)
    assert store.get_position(0x05010203) == 42

    # removal is observable.
    store.db_remove_device_by_field("uid", "UID1")
    assert store.db_get_device_by_field("uid", "UID1") is None


def test_sqlite_store_fulfils_device_store_contract(tmp_path):
    check_device_store_contract(SqliteDeviceStore({"db_file": str(tmp_path / "db.sqlite")}))
