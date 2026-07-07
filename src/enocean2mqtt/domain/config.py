"""The ``Config`` value object — the daemon's validated, typed configuration.

``Config`` is a read-only ``Mapping`` backed by the raw options dict, so dict-style ``.get`` /
``[]`` / ``in`` reads work, and it also exposes typed accessors (``config.mqtt_host``,
``config.send_interval_ms``, …), which callers prefer. ``from_mapping`` validates the mandatory
keys once, at the composition root, instead of the daemon raising deep in ``__init__``.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping

from enocean2mqtt.config import as_bool

_MANDATORY = ("mqtt_host", "enocean_port")


class Config(Mapping):
    """Typed, read-only view over the raw options mapping (a drop-in for the old ``conf`` dict)."""

    def __init__(self, raw: Mapping):
        self._raw = dict(raw)

    @classmethod
    def from_mapping(cls, raw: Mapping) -> Config:
        """Build a Config, validating that the mandatory keys are present."""
        if isinstance(raw, Config):
            return raw
        missing = [k for k in _MANDATORY if k not in raw]
        if missing:
            raise ValueError(f"Mandatory configuration not found: {', '.join(missing)}")
        return cls(raw)

    # --- Mapping facade (dict-style access) --------------------------------------------------
    def __getitem__(self, key: str):
        return self._raw[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._raw)

    def __len__(self) -> int:
        return len(self._raw)

    # --- typed accessors ----------------------------------------------------------------------
    # Connection
    @property
    def mqtt_host(self) -> str:
        return self._raw["mqtt_host"]

    @property
    def enocean_port(self) -> str:
        return self._raw["enocean_port"]

    @property
    def mqtt_port(self) -> int:
        return int(self._raw.get("mqtt_port", 1883))

    @property
    def mqtt_keepalive(self) -> int:
        return int(self._raw.get("mqtt_keepalive", 60))

    @property
    def mqtt_user(self) -> str | None:
        return self._raw.get("mqtt_user")

    @property
    def mqtt_pwd(self) -> str | None:
        return self._raw.get("mqtt_pwd")

    @property
    def mqtt_client_id(self) -> str | None:
        return self._raw.get("mqtt_client_id") or None

    @property
    def mqtt_prefix(self) -> str:
        return self._raw.get("mqtt_prefix", "enocean/")

    @property
    def send_interval_ms(self) -> int:
        return int(self._raw.get("send_interval_ms", 100))

    @property
    def secure_psk(self) -> str | None:
        """Pre-shared key (32 hex) for decrypting PSK-protected secure teach-ins; None if unset."""
        psk = self._raw.get("secure_psk")
        return str(psk).strip() if psk else None

    @property
    def repeater_level(self) -> int | None:
        """Repeater level from the ``repeater`` option: 0 (off), 1, or 2. None if unset/unknown."""
        raw = self._raw.get("repeater")
        if raw is None or str(raw).strip() == "":
            return None
        text = str(raw).strip().lower()
        if text in ("off", "0", "false", "no"):
            return 0
        if text in ("1", "2"):
            return int(text)
        return None

    @property
    def overlay(self) -> str:
        return str(self._raw.get("overlay", "")).lower()

    @property
    def log_level(self) -> str:
        return str(self._raw.get("log_level", "info")).lower()

    # TLS
    @property
    def mqtt_ssl(self) -> bool:
        return as_bool(self._raw.get("mqtt_ssl"))

    @property
    def mqtt_ssl_ca_certs(self) -> str | None:
        return self._raw.get("mqtt_ssl_ca_certs")

    @property
    def mqtt_ssl_certfile(self) -> str | None:
        return self._raw.get("mqtt_ssl_certfile")

    @property
    def mqtt_ssl_keyfile(self) -> str | None:
        return self._raw.get("mqtt_ssl_keyfile")

    @property
    def mqtt_ssl_insecure(self) -> bool:
        return as_bool(self._raw.get("mqtt_ssl_insecure"))

    # Home Assistant overlay
    @property
    def mqtt_discovery_prefix(self) -> str:
        return self._raw.get("mqtt_discovery_prefix", "homeassistant/")

    @property
    def ha_dev_name_in_entity(self) -> bool:
        return as_bool(self._raw.get("ha_dev_name_in_entity"))
