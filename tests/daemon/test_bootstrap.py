"""The composition root (bootstrap) + the typed Config value object."""

from unittest import mock

import pytest

from enocean2mqtt.application.bootstrap import bootstrap
from enocean2mqtt.application.daemon import EnoceanDaemon
from enocean2mqtt.domain.config import Config

BASE = {"mqtt_host": "broker", "enocean_port": "socket://127.0.0.1:3000"}


def test_config_typed_accessors_and_defaults():
    cfg = Config.from_mapping(
        {**BASE, "mqtt_port": "1884", "send_interval_ms": "50", "mqtt_ssl": "1"}
    )
    assert cfg.mqtt_host == "broker"
    assert cfg.mqtt_port == 1884  # coerced from str
    assert cfg.send_interval_ms == 50
    assert cfg.mqtt_ssl is True
    # defaults
    assert Config.from_mapping(BASE).mqtt_port == 1883
    assert Config.from_mapping(BASE).mqtt_prefix == "enocean/"
    assert Config.from_mapping(BASE).mqtt_discovery_prefix == "homeassistant/"


def test_config_is_dict_compatible():
    cfg = Config.from_mapping({**BASE, "overlay": "HA"})
    # legacy .get / [] / in still work (drop-in for the old conf dict)
    assert cfg.get("mqtt_host") == "broker"
    assert cfg["overlay"] == "HA"
    assert "enocean_port" in cfg and "nope" not in cfg
    assert cfg.overlay == "ha"  # typed accessor normalises case


def test_config_validates_mandatory_keys():
    with pytest.raises(ValueError, match="Mandatory configuration"):
        Config.from_mapping({"mqtt_host": "broker"})  # missing enocean_port


def test_from_mapping_is_idempotent():
    cfg = Config.from_mapping(BASE)
    assert Config.from_mapping(cfg) is cfg


def test_bootstrap_selects_base_daemon():
    com = bootstrap(BASE, [])
    assert isinstance(com, EnoceanDaemon)


def test_bootstrap_selects_ha_overlay():
    ha = mock.Mock()
    with mock.patch(
        "enocean2mqtt.homeassistant.ha_bridge.HomeAssistantBridge", mock.Mock(return_value=ha)
    ) as ha_cls:
        com = bootstrap({**BASE, "overlay": "ha"}, [])
    assert com is ha
    ha_cls.assert_called_once()
