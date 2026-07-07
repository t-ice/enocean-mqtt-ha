"""Strategy: the parts of HA MQTT-discovery that differ between EEP-based and model-based devices.

The shared discovery skeleton lives in :class:`DiscoveryPublisher`; each ``MappingLookup`` supplies
the ~28% that differs — how to resolve the entity map, the device UID, the device name, the entity
topic base, the HA ``device`` block, and any per-entity overrides.
"""

from __future__ import annotations

import copy
from abc import ABC, abstractmethod


class MappingLookup(ABC):
    """Strategy base: the discovery details that differ per device kind. Subclasses must implement
    the identity/resolution hooks; :meth:`apply_entity_override` has a no-op default."""

    def __init__(self, sensor, ha_mapping, mqtt_prefix):
        self._sensor = sensor
        self._mapping = ha_mapping
        self._mqtt_prefix = mqtt_prefix

    # --- identity used by the publisher + logging ---
    @property
    @abstractmethod
    def label(self) -> str:  # e.g. "F6-02-01" (EEP) or "eltako_FSR14" (ref)
        ...

    @property
    @abstractmethod
    def log_kind(self) -> str:  # "EEP" or "REF"
        ...

    @property
    @abstractmethod
    def topic_base(self) -> str:  # base for entity state/command topics + the __system subscribe
        ...

    @property
    @abstractmethod
    def dev_name(self) -> str: ...

    @abstractmethod
    def resolve_entities(self, is_virtual):
        """Return the entity list from the mapping (deep-copied), or None if unsupported."""
        ...

    @abstractmethod
    def dev_uid(self, address, sender) -> str: ...

    @abstractmethod
    def device_block(self, address, sender, dev_uid) -> dict: ...

    def apply_entity_override(self, entity, cfg) -> None:  # noqa: B027 - optional hook, no-op default
        """Optional per-entity tweak before topic-prefixing (default: none)."""

    # shared helper
    def _entities(self, node, is_virtual):
        try:
            return copy.deepcopy(node["virtual" if is_virtual else "entities"])
        except KeyError:
            return None


class EepMappingLookup(MappingLookup):
    def __init__(self, sensor, ha_mapping, mqtt_prefix):
        super().__init__(sensor, ha_mapping, mqtt_prefix)
        self._rorg, self._func, self._type = sensor.rorg, sensor.func, sensor.type
        self._eep_dash = f"{self._rorg:02X}-{self._func:02X}-{self._type:02X}"
        self._eep = format((self._rorg << 16) + (self._func << 8) + self._type, "06X")

    @property
    def label(self):
        return self._eep_dash

    @property
    def log_kind(self):
        return "EEP"

    @property
    def topic_base(self):
        return self._sensor.name

    @property
    def dev_name(self):
        return "e2m_" + self._sensor.name.replace(self._mqtt_prefix, "").replace("/", "_")

    def resolve_entities(self, is_virtual):
        try:
            return self._entities(self._mapping[self._rorg][self._func][self._type], is_virtual)
        except KeyError:
            return None

    def dev_uid(self, address, sender):
        return self._eep + "_" + address + "_" + sender

    def device_block(self, address, sender, dev_uid):
        return {
            "name": self.dev_name,
            "identifiers": address if address != "FFFFFFFF" else dev_uid,
            "model": (
                self._eep_dash + " @" + address
                if address != "FFFFFFFF"
                else self._eep_dash + " (VIRTUAL) / " + sender + "->" + address
            ),
            "manufacturer": "EnOcean",
            "configuration_url": (
                "http://tools.enocean-alliance.org/EEPViewer/profiles/"
                + self._eep_dash.replace("-", "/")
                + "/"
                + self._eep_dash
                + ".pdf"
            ),
        }


class ModelMappingLookup(MappingLookup):
    def __init__(self, sensor, ha_mapping, mqtt_prefix):
        super().__init__(sensor, ha_mapping, mqtt_prefix)
        self._model = sensor.model
        self._manufacturer = sensor.manufacturer
        self._reference = self._manufacturer + "_" + self._model
        self._name = sensor.name[:-3]  # strip the "/RORG" suffix

    @property
    def label(self):
        return self._reference

    @property
    def log_kind(self):
        return "REF"

    @property
    def topic_base(self):
        return self._name

    @property
    def dev_name(self):
        return "e2m_" + self._name.replace(self._mqtt_prefix, "").replace("/", "_")

    def resolve_entities(self, is_virtual):
        try:
            return self._entities(self._mapping[self._manufacturer][self._model], is_virtual)
        except KeyError:
            return None

    def dev_uid(self, address, sender):
        return self._reference + "_" + address + "_" + sender

    def device_block(self, address, sender, dev_uid):
        return {
            "name": self.dev_name,
            "identifiers": address if address != "FFFFFFFF" else dev_uid,
            "model": (
                self._model.upper() + " @" + address
                if address != "FFFFFFFF"
                else self._model.upper() + " (VIRTUAL) / " + sender + "->" + address
            ),
            "manufacturer": self._manufacturer,
            "configuration_url": (
                "https://www.google.com/search?q=" + self._manufacturer + "+" + self._model + "+pdf"
            ),
        }

    def apply_entity_override(self, entity, cfg):
        # Models read RSSI/last_seen from the next MQTT level.
        if str(entity.get("name")).lower() in ("rssi", "last_seen"):
            cfg["state_topic"] = "+"
