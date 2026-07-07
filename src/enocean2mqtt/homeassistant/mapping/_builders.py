"""Small factories for the HA MQTT-discovery ``MAPPING`` (see ``mapping.py``).

``mapping.py`` is a large data structure of per-EEP / per-model discovery entities. These helpers
carry the repeated scaffolding (the empty ``device_config``, the ubiquitous ``state_topic: ""``, the
``value_json`` templates) so the data file states only what differs per device.

Each factory returns a **fresh** dict/list, so no two leaves ever share an object. The contract with
the data is **value equality**, not key order (dicts compare order-independently) — guarded by
``tests/ha/test_mapping.py``. Entity list order *is* significant and preserved by the caller.
"""

from __future__ import annotations

from typing import Any

from enocean2mqtt.protocol.profiles import PROFILES

Config = dict[str, Any]
Entity = dict[str, Any]


def enum_map_template(rorg: int, func: int, typ: int, shortcut: str) -> str:
    """Jinja mapping a decoded enum field to its label, sourced from the EEP profile's enum items.

    e.g. ``"{% set m = {0: 'Auto', …} %}{{ m.get(value_json.FS | int, value_json.FS) }}"``. Keeps
    the HA labels in sync with the decode profile (single source of truth).
    """
    field = next(
        f
        for c in PROFILES[(rorg, func, typ)].cases
        for f in c.fields
        if f.shortcut == shortcut and f.items
    )
    labels = {item.value: item.description for item in field.items}
    return (
        f"{{% set m = {labels!r} %}}"
        f"{{{{ m.get(value_json.{shortcut} | int, value_json.{shortcut}) }}}}"
    )


def dcfg(
    command: str = "",
    channel: str = "",
    log_learn: str = "",
    direction: str = "",
    answer: str = "",
) -> Config:
    """The per-device ``device_config`` overlaid onto a sensor (command/channel/… attributes)."""
    return {
        "command": command,
        "channel": channel,
        "log_learn": log_learn,
        "direction": direction,
        "answer": answer,
    }


def dcfg_gw(
    rorg: str,
    func: str,
    typ: str,
    command: str = "",
    channel: str = "",
    log_learn: str = "",
    direction: str = "",
    answer: str = "",
) -> list[Config]:
    """Gateway ``device_config`` pinning the outbound EEP (Eltako A5-38-08 / A5-3F-7F)."""
    return [
        {
            "rorg": rorg,
            "func": func,
            "type": typ,
            "command": command,
            "channel": channel,
            "log_learn": log_learn,
            "direction": direction,
            "answer": answer,
        }
    ]


def vt(field: str, filt: str | None = None) -> str:
    """A ``value_json.<field>`` template, optionally piped through a filter (e.g. ``round(1)``)."""
    suffix = f" | {filt}" if filt else ""
    return "{{ value_json." + field + suffix + " }}"


def entity(component: str, name: str, **config: Any) -> Entity:
    """Generic entity ``{component, name, config}`` — used for the less common component types."""
    return {"component": component, "name": name, "config": dict(config)}


def sensor(
    name: str,
    template: str,
    *,
    device_class: str | None = None,
    state_class: str | None = None,
    unit: str | None = None,
    icon: str | None = None,
    enabled_by_default: bool | None = None,
    state_topic: str = "",
) -> Entity:
    """A ``sensor`` entity; only the provided optional keys are emitted."""
    config: Config = {"state_topic": state_topic}
    if device_class is not None:
        config["device_class"] = device_class
    if state_class is not None:
        config["state_class"] = state_class
    if unit is not None:
        config["unit_of_measurement"] = unit
    if icon is not None:
        config["icon"] = icon
    if enabled_by_default is not None:
        config["enabled_by_default"] = enabled_by_default
    config["value_template"] = template
    return {"component": "sensor", "name": name, "config": config}


def binary(
    name: str,
    template: str,
    *,
    device_class: str | None = None,
    payload_on: str | None = None,
    payload_off: str | None = None,
    state_topic: str = "",
) -> Entity:
    """A ``binary_sensor`` entity; only the provided optional keys are emitted."""
    config: Config = {"state_topic": state_topic}
    if device_class is not None:
        config["device_class"] = device_class
    if payload_on is not None:
        config["payload_on"] = payload_on
    if payload_off is not None:
        config["payload_off"] = payload_off
    config["value_template"] = template
    return {"component": "binary_sensor", "name": name, "config": config}
