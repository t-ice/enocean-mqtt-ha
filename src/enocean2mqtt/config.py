"""Small configuration helpers."""


def as_bool(value: object) -> bool:
    """Interpret a config/sensor value as a boolean.

    Values reach the daemon as strings (from the INI config and the device files) and occasionally
    as real ``bool``/``int``. A value is truthy iff its string form is ``"True"``, ``"true"`` or
    ``"1"`` — this preserves the exact truthiness the daemon has always used, replacing the
    ``str(x) in ("True", "true", "1")`` idiom that was repeated throughout the code.
    """
    return str(value) in ("True", "true", "1")
