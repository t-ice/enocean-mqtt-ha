"""as_bool must treat only ``str(x) in ("True", "true", "1")`` as truthy."""

import pytest

from enocean2mqtt.config import as_bool


@pytest.mark.parametrize(
    "value,expected",
    [
        ("True", True),
        ("true", True),
        ("1", True),
        (1, True),
        (True, True),
        ("False", False),
        ("false", False),
        ("0", False),
        (0, False),
        (False, False),
        (None, False),
        ("", False),
        ("yes", False),
        ("TRUE", False),  # only the exact-case forms are truthy, as before
    ],
)
def test_as_bool_matches_legacy_truthiness(value, expected):
    assert as_bool(value) is expected
    # equivalence with the exact idiom it replaces
    assert as_bool(value) == (str(value) in ("True", "true", "1"))
