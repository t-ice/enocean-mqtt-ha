"""sqlite device store: legacy TinyDB migration, device lifecycle, cover-position persistence."""

import json

from enocean2mqtt.adapters.store.sqlite_store import SqliteDeviceStore

_SENSOR = {
    "name": "e/Wetter",
    "address": 0x059ED79A,
    "rorg": 0xA5,
    "func": 0x13,
    "type": 0x01,
}


def _store(tmp_path, name="db.sqlite"):
    return SqliteDeviceStore({"db_file": str(tmp_path / name)})


def test_add_get_and_reject_duplicate(tmp_path):
    s = _store(tmp_path)
    assert s.db_add_device(_SENSOR, "uid-1") is True
    assert s.db_get_device_by_address(0x059ED79A)["name"] == "e/Wetter"
    assert s.db_list_from_fields("uid") == ["uid-1"]
    # a second add for the same address is refused
    assert s.db_add_device(_SENSOR, "uid-2") is False


def test_update_and_remove(tmp_path):
    s = _store(tmp_path)
    s.db_add_device(_SENSOR, "uid-1")
    renamed = {**_SENSOR, "uid": "uid-1", "name": "e/Weather"}
    assert s.db_update_device(renamed, "uid-1") is True  # rename, same uid
    assert s.db_get_device_by_field("uid", "uid-1")["name"] == "e/Weather"
    assert s.db_remove_device_by_field("uid", "uid-1") is True
    assert s.db_get_device_by_address(0x059ED79A) is None
    assert s.db_remove_device_by_address(0x059ED79A) is False  # already gone
    assert s.db_update_device(renamed, "uid-1") is False  # nothing to update now


def test_upsert_eep_and_model(tmp_path):
    s = _store(tmp_path)
    s.db_upsert_device(_SENSOR, "uid-eep")
    assert s.db_get_device_by_field("uid", "uid-eep")["rorg"] == 0xA5
    model = {"name": "e/Rollo/f6", "address": 0xFF94CE9C, "model": "eltako/fsb14"}
    s.db_upsert_device(model, "uid-model")
    got = s.db_get_device_by_field("uid", "uid-model")
    assert got["model"] == "eltako/fsb14" and got["name"] == "e/Rollo"  # "/f6" suffix stripped


def test_position_persists_across_reopen(tmp_path):
    s = _store(tmp_path)
    s.db_add_device(_SENSOR, "uid-1")
    assert s.get_position(0x059ED79A) is None
    s.set_position(0x059ED79A, 73)
    assert s.get_position(0x059ED79A) == 73
    # a fresh store on the same file sees the persisted position
    assert _store(tmp_path).get_position(0x059ED79A) == 73


def test_upsert_preserves_position_and_rlc(tmp_path):
    """Discovery runs db_upsert_device on every (re)connect; it must MERGE onto the existing row so
    runtime state (cover position, secure rolling codes) isn't wiped. Regression: the upsert built a
    fresh doc without these fields, so a reconnect reset the position to unknown."""
    s = _store(tmp_path)
    model = {"name": "e/Rollo/a5", "address": 0xFF94CE9C, "model": "eltako/fsb14"}
    s.db_upsert_device(model, "uid-model")
    s.set_position(0xFF94CE9C, 55)
    s.set_rlc(0xFF94CE9C, rlc=1234)

    # A second upsert (as a reconnect's discovery would issue) must keep position + rlc.
    s.db_upsert_device(model, "uid-model", "cfgtopics", ["cover/x/config"])

    assert s.get_position(0xFF94CE9C) == 55
    assert s.get_rlc(0xFF94CE9C) == (1234, None)
    assert s.db_get_device_by_field("uid", "uid-model")["cfgtopics"] == ["cover/x/config"]


def test_rlc_persists_across_reopen(tmp_path):
    s = _store(tmp_path)
    s.db_add_device(_SENSOR, "uid-1")
    assert s.get_rlc(0x059ED79A) == (None, None)
    s.set_rlc(0x059ED79A, rlc=0x123456, rlc_snd=0x0000AA)
    assert s.get_rlc(0x059ED79A) == (0x123456, 0x0000AA)
    # a fresh store on the same file sees the persisted rolling codes
    assert _store(tmp_path).get_rlc(0x059ED79A) == (0x123456, 0x0000AA)


def test_migrates_legacy_tinydb_json(tmp_path):
    legacy = tmp_path / "enocean2mqtt_db.json"
    legacy.write_text(
        json.dumps(
            {
                "_default": {
                    "1": {"uid": "u1", "address": 1, "name": "e/a", "position": 40},
                    "2": {"uid": "u2", "address": 2, "name": "e/b"},
                }
            }
        ),
        encoding="utf-8",
    )
    s = SqliteDeviceStore({"db_file": str(legacy)})  # .json path → derives .sqlite + migrates
    assert set(s.db_list_from_fields("uid")) == {"u1", "u2"}
    assert s.get_position(1) == 40


def test_corrupt_legacy_json_is_backed_up_not_fatal(tmp_path):
    legacy = tmp_path / "enocean2mqtt_db.json"
    legacy.write_text("{ this is not valid json", encoding="utf-8")
    s = SqliteDeviceStore({"db_file": str(legacy)})  # must not raise
    assert s.db_list_from_fields("uid") == []
    assert list(tmp_path.glob("enocean2mqtt_db.json.corrupt.*"))  # backed up
