"""The ``Sensor`` value object — a device's configuration plus per-send runtime scratch.

``Sensor`` is a ``MutableMapping`` backed by an internal dict, so dict-style access the encoder
and inbound router rely on — membership (``"raw_data" in sensor``), ``get``, ``[]``, ``del`` —
works, and it compares equal to an equivalent plain dict. It also exposes **typed attribute
accessors** (``sensor.rorg``, ``sensor.raw_data``), which callers prefer.

``from_dict``/``to_dict`` bridge the config loaders and the sqlite device store (which persists its
own documents, not ``Sensor`` objects).
"""

from __future__ import annotations

from collections.abc import Iterator, MutableMapping
from typing import Any

# Every modelled key. `name` is mandatory; the rest are optional and absent unless set — presence is
# meaningful (the encoder/inbound test ``"raw_data" in sensor`` etc.), so accessors read via .get().
_CONFIG_FIELDS = (
    "name",
    "address",
    "rorg",
    "func",
    "type",
    "model",
    "manufacturer",
    "sender",
    "command",
    "channel",
    "direction",
    "answer",
    "log_learn",
    "default_data",
    "publish_json",
    "publish_rssi",
    "publish_date",
    "persistent",
    "ignore",
    "shut_time",
    "virtual",
    "security",
    "key",
    "rlc",
    "slf",
    "key_snd",
    "rlc_snd",
)
# Runtime scratch set/cleared per send by the inbound router (not configuration).
_RUNTIME_FIELDS = ("learn", "raw_data", "data")


class Sensor(MutableMapping):
    """A configured EnOcean device (+ runtime send scratch). Dict-compatible during migration."""

    def __init__(self, **values: Any) -> None:
        self._d: dict[str, Any] = dict(values)

    @classmethod
    def from_dict(cls, values: Any) -> Sensor:
        """Build a Sensor from a plain dict (or return it unchanged if already a Sensor)."""
        if isinstance(values, Sensor):
            return values
        return cls(**dict(values))

    def to_dict(self) -> dict[str, Any]:
        """A plain-dict copy (for the sqlite store and for serialisation)."""
        return dict(self._d)

    # --- MutableMapping: exact legacy-dict semantics ---------------------------------------------
    def __getitem__(self, key: str) -> Any:
        return self._d[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._d[key] = value

    def __delitem__(self, key: str) -> None:
        del self._d[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._d)

    def __len__(self) -> int:
        return len(self._d)

    def __repr__(self) -> str:
        return f"Sensor({self._d!r})"

    # --- typed attribute reads (None when the key is absent) -------------------------------------
    @property
    def name(self) -> str | None:
        return self._d.get("name")

    @property
    def address(self) -> int | None:
        return self._d.get("address")

    @property
    def rorg(self) -> int | None:
        return self._d.get("rorg")

    @property
    def func(self) -> int | None:
        return self._d.get("func")

    @property
    def type(self) -> int | None:
        return self._d.get("type")

    @property
    def model(self) -> str | None:
        return self._d.get("model")

    @property
    def manufacturer(self) -> str | None:
        return self._d.get("manufacturer")

    @property
    def sender(self) -> int | None:
        return self._d.get("sender")

    @property
    def command(self) -> str | None:
        return self._d.get("command")

    @property
    def channel(self) -> str | None:
        return self._d.get("channel")

    @property
    def direction(self) -> Any:
        return self._d.get("direction")

    @property
    def answer(self) -> Any:
        return self._d.get("answer")

    @property
    def log_learn(self) -> Any:
        return self._d.get("log_learn")

    @property
    def default_data(self) -> str | None:
        return self._d.get("default_data")

    @property
    def ignore(self) -> Any:
        return self._d.get("ignore")

    @property
    def shut_time(self) -> int | None:
        return self._d.get("shut_time")

    @property
    def virtual(self) -> Any:
        return self._d.get("virtual")

    # secure telegrams (P5): per-device AES key / rolling code / security-level-format byte
    @property
    def security(self) -> Any:
        return self._d.get("security")

    @property
    def key(self) -> str | None:
        return self._d.get("key")

    @property
    def rlc(self) -> int | None:
        return self._d.get("rlc")

    @property
    def slf(self) -> int | None:
        return self._d.get("slf")

    @property
    def key_snd(self) -> str | None:
        return self._d.get("key_snd")

    @property
    def rlc_snd(self) -> int | None:
        return self._d.get("rlc_snd")

    # runtime scratch
    @property
    def learn(self) -> bool:
        return bool(self._d.get("learn"))

    @property
    def raw_data(self) -> str | None:
        return self._d.get("raw_data")

    @property
    def data(self) -> dict | None:
        return self._d.get("data")

    @property
    def has_raw_data(self) -> bool:
        return "raw_data" in self._d

    # --- typed runtime-scratch mutators (replace ad-hoc dict mutation in the inbound router) ---
    def mark_learn(self) -> None:
        """Flag the next send as a teach-in telegram."""
        self._d["learn"] = True

    def clear_learn(self) -> None:
        self._d.pop("learn", None)

    def set_raw_data(self, raw: str) -> None:
        self._d["raw_data"] = raw

    def clear_raw_data(self) -> None:
        self._d.pop("raw_data", None)

    def accumulate(self, prop: str, value: Any) -> None:
        """Record one property for the next send (properties accrue across MQTT messages)."""
        self._d.setdefault("data", {})[prop] = value

    def accumulate_many(self, values: dict) -> None:
        """Record several properties at once (bulk JSON payload)."""
        self._d.setdefault("data", {}).update(values)

    def clear_data(self) -> None:
        self._d.pop("data", None)
