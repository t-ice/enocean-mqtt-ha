"""cli.load_config_file (YAML devices + [CONFIG] + INI guard) and main() overlay selection."""

import textwrap
from unittest import mock

import pytest

from enocean2mqtt import cli


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return str(p)


def test_load_conf_reads_config_section_only(tmp_path):
    conf = _write(
        tmp_path,
        "e.conf",
        """
        [CONFIG]
        mqtt_host = broker
        mqtt_prefix = enocean2mqtt/
        overlay = HA
    """,
    )
    sensors, global_config = cli.load_config_file([conf])
    assert sensors == []
    assert global_config["mqtt_host"] == "broker" and global_config["overlay"] == "HA"


def test_load_devices_yaml_appends_sensors(tmp_path):
    conf = _write(tmp_path, "e.conf", "[CONFIG]\nmqtt_prefix = e/\n")
    _write(
        tmp_path,
        "devices.yaml",
        """
        devices:
          - name: Wetter
            address: 0x059ED79A
            eep: A5-13-01
    """,
    )
    sensors, _ = cli.load_config_file([conf, str(tmp_path / "devices.yaml")])
    assert len(sensors) == 1 and sensors[0]["name"] == "e/Wetter" and sensors[0].rorg == 0xA5


def test_missing_config_file_is_skipped(tmp_path, caplog):
    sensors, global_config = cli.load_config_file([str(tmp_path / "nope.conf")])
    assert sensors == [] and global_config == {}
    assert "does not exist" in caplog.text


def _run_main(monkeypatch, overlay):
    monkeypatch.setattr(cli, "parse_args", lambda: {})
    monkeypatch.setattr(cli, "setup_logging", lambda *a, **k: None)
    sensors = [{"name": "e/x", "sender": 1}, {"name": "e/y", "sender": 1}]  # dup sender → logged
    # mqtt_host/enocean_port are mandatory (validated at the composition root).
    cfg = {"overlay": overlay, "mqtt_host": "x", "enocean_port": "socket://127.0.0.1:3000"}
    monkeypatch.setattr(cli, "load_config_file", lambda _c: (sensors, cfg))


def test_main_selects_base_communicator(monkeypatch):
    _run_main(monkeypatch, overlay="none")
    com = mock.Mock()
    # overlay selection lives in the composition root now
    monkeypatch.setattr(
        "enocean2mqtt.application.bootstrap.EnoceanDaemon", mock.Mock(return_value=com)
    )
    cli.main()
    com.run.assert_called_once()


def test_main_selects_ha_overlay(monkeypatch):
    _run_main(monkeypatch, overlay="ha")
    ha = mock.Mock()
    ha_cls = mock.Mock(return_value=ha)
    monkeypatch.setattr("enocean2mqtt.homeassistant.ha_bridge.HomeAssistantBridge", ha_cls)
    cli.main()
    ha_cls.assert_called_once()
    ha.run.assert_called_once()


@pytest.mark.parametrize(
    ("option", "expected"),
    [("error", "ERROR"), ("warning", "WARNING"), ("info", "INFO"), ("debug", "DEBUG")],
)
def test_log_level_option_maps_to_logging_level(monkeypatch, option, expected):
    """--log-level selects the Python logging level passed to setup_logging (default info)."""
    import logging

    captured = {}
    monkeypatch.setattr(cli, "parse_args", lambda: {"log_level": option})
    monkeypatch.setattr(
        cli, "setup_logging", lambda _f, level: captured.__setitem__("level", level)
    )
    monkeypatch.setattr(
        cli,
        "load_config_file",
        lambda _c: ([], {"overlay": "none", "mqtt_host": "x", "enocean_port": "p"}),
    )
    monkeypatch.setattr(
        "enocean2mqtt.application.bootstrap.EnoceanDaemon", mock.Mock(return_value=mock.Mock())
    )
    cli.main()
    assert captured["level"] == getattr(logging, expected)


def test_setup_logging_uses_rotating_file_handler(tmp_path, monkeypatch):
    """The file handler is size-capped (RotatingFileHandler) and rolls at the cap."""
    import logging
    import logging.handlers

    monkeypatch.setattr(cli, "_LOG_MAX_BYTES", 512)
    monkeypatch.setattr(cli, "_LOG_BACKUP_COUNT", 2)
    log_path = tmp_path / "enocean2mqtt.log"

    root = logging.getLogger()
    saved = root.handlers[:]
    root.handlers = []
    try:
        cli.setup_logging(str(log_path), logging.INFO)
        file_handlers = [
            h for h in root.handlers if isinstance(h, logging.handlers.RotatingFileHandler)
        ]
        assert len(file_handlers) == 1
        assert file_handlers[0].maxBytes == 512 and file_handlers[0].backupCount == 2

        for _ in range(200):  # well over the 512-byte cap
            logging.info("x" * 50)
        assert log_path.with_suffix(".log.1").exists()  # rolled backup created
    finally:
        for h in root.handlers:
            h.close()
        root.handlers = saved
