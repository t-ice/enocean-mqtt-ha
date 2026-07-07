"""HA MQTT-discovery mapping (rorg->func->type + model/system entity definitions).

The catalog is split into per-family fragments under ``eep/`` for readability; they are merged
here into the single ``MAPPING`` the overlay consumes (deep-copied once by the HA bridge). Value
is checked by ``tests/ha/test_mapping.py``.
"""

from enocean2mqtt.homeassistant.mapping.eep import (
    a5_hvac,
    a5_room_panels,
    a5_sensors,
    a5_weather,
    d2_devices,
    d2_switches,
    eltako,
    f6,
    misc,
)

_FRAGMENTS = (
    a5_sensors,
    a5_room_panels,
    a5_hvac,
    a5_weather,
    d2_switches,
    d2_devices,
    f6,
    eltako,
    misc,
)

MAPPING: dict = {}
for _frag in _FRAGMENTS:
    for _key, _sub in _frag.MAPPING.items():
        if isinstance(_key, int):  # RORG -> union its func dicts across fragments
            MAPPING.setdefault(_key, {}).update(_sub)
        else:  # 'eltako' / 'common' / 'system'
            MAPPING[_key] = _sub

__all__ = ["MAPPING"]
