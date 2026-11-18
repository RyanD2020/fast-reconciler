"""
Timing research for Phase 3: which bank lines pay for which Cadency day.

Cadency posts a day's reclaims on one date; the bank receives them in
batches that don't respect that date. In Sean's September 2026 test data
(2026-11-18), most Cadency post days tie to the cent with bank lines from
the same day plus the next or previous day with activity -- e.g. 9/1's
reclaims, net of DCU splits, are two 9/1 bank lines plus one that landed on
9/2. A strict same-day compare calls 15 of 16 days breaks; once timing is
allowed for, 11 of the 14 Cadency days tie and three items are left -- the
same three Sean had annotated by hand in that file (two "suppression"
reclaims and one bank line with no reclaim).

allocate() does that research in four passes, each working only on what
the earlier passes left open:
  1. Same day: a day whose own bank lines total its Cadency amount keeps them.
  2. Timing: a day ties to some combination of still-unclaimed bank lines
     dated within `window` activity days either side of it.
  3. Runs: consecutive open days tie together (e.g. a Friday and a Monday
     whose batches straddle the weekend differently).
  4. One reclaim short: the day (or run) ties exactly once a single Cadency
     reclaim is set aside -- that reclaim never reached the bank.
Whatever is still open after that is unexplained, and any bank line nobody
claimed has no Cadency reclaim behind it.

Amounts are integer cents, so "ties" means exactly to the cent -- the same
zero tolerance as the rest of the tool. Nothing here changes a day's
RECONCILED / DOES NOT RECONCILE status; it only explains it.

"Activity day" = any date with a Cadency post or a bank line, so weekends and
holidays (Labor Day sits inside the September data) are skipped without a
calendar. The window is a working assumption, not a confirmed business rule
(AccountConfig.phase3_timing_window_days).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

# A window is searched by trying every combination of its bank lines: 2**16
# is ~65k sums, instant. A month of +166 activity has 1-4 lines a day.
MAX_SEARCH_LINES = 16


@dataclass(frozen=True)
class Entry:
    """One Cadency reclaim or one bank line. key is the caller's row label
    (must be unique within its list), so results can be mapped back."""

    key: object
    day: date
    cents: int


@dataclass(frozen=True)
class Tie:
    """Cadency days and the bank lines that pay for them, to the cent."""

    days: tuple[date, ...]
    lines: tuple[Entry, ...]
    set_aside: Entry | None = None  # pass 4: the reclaim these days tie without

    @property
    def spans_days(self) -> bool:
        """True when the tie needed more than the day itself: several Cadency
        days together, or bank lines dated on another day."""
        return len(self.days) > 1 or any(line.day not in self.days for line in self.lines)

    @property
    def is_timing(self) -> bool:
        return self.set_aside is None and self.spans_days


@dataclass(frozen=True)
class Unexplained:
    """Cadency days nothing could tie, and the unclaimed bank lines in their window."""

    days: tuple[date, ...]
    lines: tuple[Entry, ...]
    searched: bool = True  # False when the window held more than MAX_SEARCH_LINES lines


@dataclass
class Allocation:
    ties: list[Tie] = field(default_factory=list)
    unexplained: list[Unexplained] = field(default_factory=list)
    unclaimed: list[Entry] = field(default_factory=list)  # bank lines with no Cadency reclaim behind them

    def same_day_ties(self) -> list[Tie]:
        return [t for t in self.ties if t.set_aside is None and not t.is_timing]

    def timing_ties(self) -> list[Tie]:
        return [t for t in self.ties if t.is_timing]

    def set_aside_ties(self) -> list[Tie]:
        return [t for t in self.ties if t.set_aside is not None]


def allocate(reclaims: list[Entry], lines: list[Entry], window: int = 1) -> Allocation:
    expected: dict[date, int] = defaultdict(int)
    reclaims_by_day: dict[date, list[Entry]] = defaultdict(list)
    for r in reclaims:
        expected[r.day] += r.cents
        reclaims_by_day[r.day].append(r)
    days = sorted(expected)
    calendar = sorted(set(days) | {line.day for line in lines})
    position = {d: i for i, d in enumerate(calendar)}
    free = {line.key: line for line in sorted(lines, key=lambda line: line.day)}
    result = Allocation()

    def window_lines(first: date, last: date) -> list[Entry]:
        lo = calendar[max(position[first] - window, 0)]
        hi = calendar[min(position[last] + window, len(calendar) - 1)]
        return [line for line in free.values() if lo <= line.day <= hi]

    def claim(chosen) -> tuple[Entry, ...]:
        for line in chosen:
            del free[line.key]
        return tuple(chosen)

    # 1. Same day.
    open_days = []
    for d in days:
        own = [line for line in free.values() if line.day == d]
        if sum(line.cents for line in own) == expected[d]:
            result.ties.append(Tie((d,), claim(own)))
        else:
            open_days.append(d)

    # 2. Timing, one day at a time.
    still_open = []
    for d in open_days:
        pool = window_lines(d, d)
        combo = _subset_sums(pool).get(expected[d]) if len(pool) <= MAX_SEARCH_LINES else None
        if combo is None:
            still_open.append(d)
        else:
            result.ties.append(Tie((d,), claim(combo)))

    # 3 + 4. Runs of consecutive open days; then one reclaim set aside.
    unexplained_runs = []
    for run in _runs(still_open, days):
        pool = window_lines(run[0], run[-1])
        if len(pool) > MAX_SEARCH_LINES:
            unexplained_runs.append((run, False))
            continue
        sums = _subset_sums(pool)
        target = sum(expected[d] for d in run)
        if len(run) > 1 and target in sums:
            result.ties.append(Tie(run, claim(sums[target])))
            continue
        candidates = [
            (item, sums[target - item.cents])
            for d in run
            for item in reclaims_by_day[d]
            if target - item.cents in sums
        ]
        if len(candidates) == 1:
            item, combo = candidates[0]
            result.ties.append(Tie(run, claim(combo), set_aside=item))
        else:
            unexplained_runs.append((run, True))

    # Leftover lines near an unexplained run are reported with it, not as
    # "no Cadency reclaim" -- they're likely part of what didn't tie.
    for run, searched in unexplained_runs:
        result.unexplained.append(Unexplained(run, claim(window_lines(run[0], run[-1])), searched))
    result.unclaimed = list(free.values())
    return result


def _subset_sums(pool: list[Entry]) -> dict[int, tuple[Entry, ...]]:
    """Every total some combination of the pool reaches -> one combination
    that reaches it (the empty combination reaches 0)."""
    sums: dict[int, tuple[Entry, ...]] = {0: ()}
    for line in pool:
        for total, combo in list(sums.items()):
            sums.setdefault(total + line.cents, combo + (line,))
    return sums


def _runs(open_days: list[date], all_days: list[date]) -> list[tuple[date, ...]]:
    """Group open days that are neighbours among the Cadency post days."""
    position = {d: i for i, d in enumerate(all_days)}
    runs: list[list[date]] = []
    for d in open_days:
        if runs and position[d] == position[runs[-1][-1]] + 1:
            runs[-1].append(d)
        else:
            runs.append([d])
    return [tuple(run) for run in runs]
