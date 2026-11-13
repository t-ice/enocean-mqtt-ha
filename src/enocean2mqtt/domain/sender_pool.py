"""Sender-ID pool: which transmit addresses a transceiver owns and which one to hand out next.

A transceiver may transmit from its Base ID plus an offset of 0..127. Offset 0 (the Base ID itself)
is the default sender of devices without a ``sender``; offsets 1..127 are handed out to actuators,
each of which is taught to obey exactly one of them.

Allocation is deliberately conservative: the next address is always *one above the highest offset
ever in use* (configured now, or remembered from an earlier start). Gaps are never filled, because
a gap may belong to an actuator that was removed from the config but still obeys its old sender —
re-using it would make the new device switch the old one as well.

Pure functions only (no I/O), so the rules are unit-testable on their own.
"""

from __future__ import annotations

from collections.abc import Iterable

# Highest offset a transceiver may add to its Base ID when transmitting.
MAX_OFFSET = 127


def in_range(base_id: int, sender: int) -> bool:
    """True if *sender* is an address this transceiver may transmit from (Base ID + 0..127)."""
    return base_id <= sender <= base_id + MAX_OFFSET


def highest_offset(base_id: int, senders: Iterable[int | None]) -> int:
    """The highest in-range offset among *senders* (0 if none; out-of-range senders don't count)."""
    offsets = [s - base_id for s in senders if s is not None and in_range(base_id, s)]
    return max(offsets, default=0)


def next_senders(
    base_id: int, used: Iterable[int | None], high_water: int, count: int
) -> list[int]:
    """Up to *count* fresh sender addresses, strictly above everything ever used.

    *used* are the senders configured right now, *high_water* the highest offset remembered from
    earlier starts. Returns fewer than *count* addresses (possibly none) when the pool runs out —
    the caller reports the devices that got nothing.
    """
    first = max(highest_offset(base_id, used), high_water, 0) + 1
    last = min(first + count - 1, MAX_OFFSET)
    return [base_id + offset for offset in range(first, last + 1)]
