"""Sender-ID pool rules: range, highest offset, and the never-re-use allocation."""

from enocean2mqtt.domain.sender_pool import MAX_OFFSET, highest_offset, in_range, next_senders

BASE = 0xFFAE7C80


def test_in_range_covers_base_id_plus_0_to_127():
    assert in_range(BASE, BASE)
    assert in_range(BASE, BASE + MAX_OFFSET)
    assert not in_range(BASE, BASE - 1)
    assert not in_range(BASE, BASE + MAX_OFFSET + 1)


def test_highest_offset_ignores_missing_and_out_of_range_senders():
    assert highest_offset(BASE, []) == 0
    assert highest_offset(BASE, [None, BASE + 3, BASE + 9, 0x0512AB34, BASE + 500]) == 9


def test_empty_config_starts_at_offset_1():
    # Offset 0 is the Base ID itself (default sender of senderless devices) and is never handed out.
    assert next_senders(BASE, [], 0, 1) == [BASE + 1]


def test_next_sender_is_above_the_highest_used_one_and_gaps_stay_free():
    used = [BASE + 1, BASE + 2, BASE + 9]  # 3..8 are gaps (maybe removed actuators) -> untouched
    assert next_senders(BASE, used, 0, 2) == [BASE + 10, BASE + 11]


def test_remembered_high_water_wins_over_the_current_config():
    # The device that once held offset 20 was deleted from the config; 20 must not come back.
    assert next_senders(BASE, [BASE + 1], 20, 1) == [BASE + 21]


def test_out_of_range_senders_do_not_influence_the_allocation():
    assert next_senders(BASE, [0xFF000001, BASE + 4], 0, 1) == [BASE + 5]


def test_pool_exhausted_returns_only_what_fits():
    assert next_senders(BASE, [BASE + 126], 0, 3) == [BASE + 127]
    assert next_senders(BASE, [BASE + 127], 0, 1) == []
    assert next_senders(BASE, [], 127, 1) == []
