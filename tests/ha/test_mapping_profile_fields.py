"""Every ``value_json.<FIELD>`` a mapping entity reads must be a real decoded field.

Links the HA MAPPING to the decode profiles: for each EEP leaf, every field referenced in a
``value_json.<FIELD>`` template must be a shortcut the profile decodes for that EEP — either a real
profile field or the special raw-telegram key. Catches typos and drift (an entity reading a field
the device/profile never emits would silently show nothing). Zero violations — no allowlist.

Shortcuts that aren't valid identifiers (e.g. ``A/PM``, ``LAT(MSB)``, ``D/N``) are referenced with
Jinja bracket notation (``value_json['A/PM']``), which this dotted-reference regex intentionally
does not match — nothing to validate there since the spelling must be the exact spec shortcut.
"""

import re

from enocean2mqtt.homeassistant.mapping import MAPPING
from enocean2mqtt.protocol.profiles import PROFILES

_REF = re.compile(r"value_json\.([A-Za-z_][A-Za-z0-9_]*)")
_SPECIAL = {"_RAW_DATA_"}


def _strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _strings(v)


def _allowed(key):
    profile = PROFILES.get(key)
    shortcuts = set()
    if profile:
        shortcuts = {f.shortcut for c in profile.cases for f in c.fields if f.shortcut}
    return shortcuts | _SPECIAL


def test_every_value_json_field_is_decoded():
    violations = {}
    for rorg, funcs in MAPPING.items():
        if not isinstance(rorg, int):  # skip 'eltako' / 'common' / 'system'
            continue
        for func, types in funcs.items():
            for typ, leaf in types.items():
                if not (isinstance(leaf, dict) and "entities" in leaf):
                    continue
                refs = set()
                for s in _strings(leaf.get("entities", [])):
                    refs |= set(_REF.findall(s))
                missing = refs - _allowed((rorg, func, typ))
                if missing:
                    violations[f"{rorg:#04x}-{func:#04x}-{typ:#04x}"] = sorted(missing)
    assert not violations, f"mapping references undecoded fields: {violations}"
