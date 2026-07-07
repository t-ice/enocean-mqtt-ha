"""Turn raw configured sensors into the HA overlay's working sensor list.

EEP-based sensors get the mapping's ``device_config`` overlaid and the HA publish flags forced on;
model-based sensors are expanded into one derived sensor per RORG entity. Pure transformation,
unit-testable in isolation.
"""

from __future__ import annotations

import contextlib
import copy
import logging

from enocean2mqtt.config import as_bool
from enocean2mqtt.domain.sensor import Sensor

logger = logging.getLogger("enocean2mqtt.homeassistant.sensor_expander")

# HA works best with JSON; also force RSSI/date/retain on every overlay sensor.
_FORCED_FLAGS = {
    "publish_json": "1",
    "publish_rssi": "1",
    "publish_date": "1",
    "persistent": "1",
}


class SensorExpander:
    def __init__(self, ha_mapping):
        self._mapping = ha_mapping

    def expand(self, sensors):
        """Return the overlay sensor list: EEP sensors overlaid + model sensors expanded."""
        models = [item for item in sensors if item.get("model")]
        sensors = [cur_sensor for cur_sensor in sensors if cur_sensor not in models]

        for cur_sensor in sensors:
            if not as_bool(cur_sensor.get("ignore")):
                self._overlay_eep_sensor(cur_sensor)

        for cur_model in models:
            if not as_bool(cur_model.get("ignore")):
                sensors.extend(self._expand_model(cur_model))

        return sensors

    def _overlay_eep_sensor(self, cur_sensor):
        """Overlay the mapping's device_config onto an EEP-based sensor and force the HA flags."""
        rorg = cur_sensor["rorg"]
        func = cur_sensor["func"]
        type_ = cur_sensor["type"]
        devcfg = {}
        with contextlib.suppress(KeyError):
            devcfg = copy.deepcopy(self._mapping[rorg][func][type_]["device_config"])

        cur_sensor["command"] = devcfg.get("command")
        cur_sensor["channel"] = devcfg.get("channel")
        cur_sensor["log_learn"] = devcfg.get("log_learn")
        cur_sensor["direction"] = devcfg.get("direction")
        cur_sensor["answer"] = devcfg.get("answer")
        cur_sensor.update(_FORCED_FLAGS)

    def _expand_model(self, cur_model):
        """Expand a model sensor into one derived sensor per RORG entity in its device_config."""
        manufacturer, model = cur_model.get("model").lower().split("/")
        logger.debug("Found new model-based device: %s %s", manufacturer, model)
        devcfg = []
        with contextlib.suppress(KeyError):
            devcfg = copy.deepcopy(self._mapping[manufacturer][model]["device_config"])

        derived = []
        for new_sens in devcfg:
            new_sens["name"] = cur_model.get("name") + "/" + new_sens.get("rorg")[2:4].lower()
            new_sens["address"] = cur_model.get("address")
            if cur_model.get("default_data"):
                new_sens["default_data"] = cur_model.get("default_data")
            if cur_model.get("sender"):
                new_sens["sender"] = cur_model.get("sender")
            if cur_model.get("ignore"):
                new_sens["ignore"] = cur_model.get("ignore")
            # Pass the configured shutter run time on so the daemon can compute the cover position.
            if cur_model.get("shut_time") is not None:
                new_sens["shut_time"] = cur_model.get("shut_time")
            new_sens["manufacturer"] = manufacturer
            new_sens["model"] = model
            new_sens["rorg"] = int(new_sens["rorg"], 0)
            new_sens["func"] = int(new_sens["func"], 0)
            new_sens["type"] = int(new_sens["type"], 0)
            new_sens.update(_FORCED_FLAGS)
            # Model-derived entries start as plain mapping dicts; wrap them so the whole sensor list
            # is uniformly Sensor objects (read via typed accessors downstream).
            derived.append(Sensor.from_dict(new_sens))
            logger.debug("Created sensor: %s", new_sens)
        return derived
