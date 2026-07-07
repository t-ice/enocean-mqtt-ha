"""Test-only ``@timing`` helper for the protocol-layer tests.

A benchmarking aid used only by these tests (it does not belong in the runtime library). Enabled
only when the ``WITH_TIMINGS=1`` environment variable is set; otherwise the decorator returns the
test unchanged.
"""

import functools
import time
from os import environ


def timing(rounds=1, limit=None):
    """Wrap a test to time it (optionally over multiple rounds), asserting an upper bound in ms."""

    def decorator(method):
        @functools.wraps(method)
        def f():
            if rounds == 1:
                start = time.time()
                method()
                duration = time.time() - start
            else:
                start = time.time()
                for _ in range(rounds):
                    method()
                duration = (time.time() - start) / rounds
            duration = duration * 1e3  # milliseconds

            print(f'Test "{method.__module__}.{method.__name__}" took {duration:.6f} ms.')
            if limit is not None:
                assert limit > duration, f"Timing failure: {duration:.6f} > {limit:.6f}"

        # Multi-round timing is slow, so only activate it under WITH_TIMINGS=1.
        if environ.get("WITH_TIMINGS", None) == "1":
            return f
        return method

    return decorator
