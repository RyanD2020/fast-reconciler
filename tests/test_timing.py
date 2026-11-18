"""
Unit tests for core.timing.allocate -- Phase 3's timing research.

The shapes here are the ones in Sean's September 2026 reclaim test data:
a day's reclaims split across its own bank day and the next, bank batches
that arrive a day early, a Friday + Monday that only tie together, and a
reclaim that never reached the bank. All amounts are synthetic.
"""

from __future__ import annotations

import unittest
from datetime import date

from core.timing import MAX_SEARCH_LINES, Entry, allocate


def d(day: int) -> date:
    return date(2026, 9, day)


class _Keys:
    def __init__(self):
        self.n = 0

    def __call__(self, day: int, dollars: float) -> Entry:
        self.n += 1
        return Entry(self.n, d(day), round(dollars * 100))


class TestAllocate(unittest.TestCase):
    def setUp(self):
        self.r, self.b = _Keys(), _Keys()

    def test_same_day_tie(self):
        a = allocate([self.r(1, 100.00), self.r(1, 50.00)], [self.b(1, 150.00)])
        self.assertEqual(len(a.same_day_ties()), 1)
        self.assertEqual(a.timing_ties(), [])
        self.assertEqual(a.unclaimed, [])

    def test_part_of_a_day_lands_on_the_next_bank_day(self):
        # 9/1's reclaims = two 9/1 lines + one 9/2 line (the real 9/1 pattern).
        a = allocate(
            [self.r(1, 900.00), self.r(1, 450.25), self.r(1, 75.10), self.r(2, 310.40)],
            [self.b(1, 1350.25), self.b(2, 75.10), self.b(2, 310.40)],
        )
        tie = next(t for t in a.ties if t.days == (d(1),))
        self.assertTrue(tie.is_timing)
        self.assertEqual(sorted(line.cents for line in tie.lines), [7510, 135025])
        self.assertEqual(len(a.same_day_ties()), 1)  # 9/2 keeps its own 310.40
        self.assertEqual(a.unclaimed, [])

    def test_bank_line_a_day_early(self):
        a = allocate([self.r(2, 40.00)], [self.b(1, 40.00)])
        self.assertTrue(a.ties[0].is_timing)

    def test_outside_the_window_is_not_a_timing_tie(self):
        # Two activity days late: window 1 can't see it, window 2 can.
        reclaims = [self.r(1, 100.00), self.r(2, 50.00)]
        lines = [self.b(2, 50.00), self.b(3, 100.00)]
        narrow = allocate(reclaims, lines, window=1)
        self.assertEqual(narrow.timing_ties(), [])
        self.assertEqual([line.cents for line in narrow.unclaimed], [10000])
        wide = allocate(reclaims, lines, window=2)
        self.assertEqual(len(wide.timing_ties()), 1)
        self.assertEqual(wide.unclaimed, [])

    def test_consecutive_days_tie_together(self):
        # Friday 9/11 + Monday 9/14 only tie as a pair.
        a = allocate(
            [self.r(11, 700.00), self.r(11, 45.00), self.r(14, 2500.00), self.r(14, 99.99)],
            [self.b(11, 1200.00), self.b(14, 2144.99)],
        )
        self.assertEqual(len(a.ties), 1)
        self.assertEqual(a.ties[0].days, (d(11), d(14)))
        self.assertTrue(a.ties[0].is_timing)

    def test_ties_once_one_reclaim_is_set_aside(self):
        missing = self.r(3, 88.88)
        a = allocate([self.r(3, 640.00), self.r(3, 129.99), missing], [self.b(3, 769.99)])
        self.assertEqual(len(a.set_aside_ties()), 1)
        self.assertEqual(a.set_aside_ties()[0].set_aside, missing)
        self.assertEqual(a.unexplained, [])

    def test_bank_line_with_no_reclaim_is_unclaimed(self):
        a = allocate([self.r(1, 100.00)], [self.b(1, 100.00), self.b(3, 123.45)])
        self.assertEqual([line.cents for line in a.unclaimed], [12345])

    def test_ambiguous_set_aside_stays_unexplained(self):
        # Two identical reclaims: either could be the missing one, so neither is picked.
        a = allocate([self.r(3, 50.00), self.r(3, 50.00), self.r(3, 20.00)], [self.b(3, 70.00)])
        self.assertEqual(a.set_aside_ties(), [])
        self.assertEqual(len(a.unexplained), 1)
        self.assertEqual([line.cents for line in a.unexplained[0].lines], [7000])

    def test_unexplained_keeps_nearby_lines(self):
        a = allocate([self.r(3, 10.00), self.r(3, 20.00)], [self.b(3, 12.34)])
        self.assertEqual(len(a.unexplained), 1)
        self.assertEqual([line.cents for line in a.unexplained[0].lines], [1234])
        self.assertEqual(a.unclaimed, [])  # reported with the unexplained day, not twice

    def test_too_many_lines_is_not_searched(self):
        lines = [self.b(1, 1.00 + i / 100) for i in range(MAX_SEARCH_LINES + 1)]
        a = allocate([self.r(1, 0.01)], lines)
        self.assertEqual(len(a.unexplained), 1)
        self.assertFalse(a.unexplained[0].searched)

    def test_fully_split_away_day_needs_no_bank_lines(self):
        a = allocate([self.r(1, 0.00)], [])
        self.assertEqual(len(a.same_day_ties()), 1)
        self.assertEqual(a.ties[0].lines, ())


if __name__ == "__main__":
    unittest.main()
