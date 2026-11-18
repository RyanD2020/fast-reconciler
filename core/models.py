from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum

import pandas as pd


class ReconStatus(str, Enum):
    RECONCILED = "RECONCILED"
    DOES_NOT_RECONCILE = "DOES NOT RECONCILE"
    MANUAL_REVIEW = "MANUAL REVIEW"


@dataclass
class DailyResult:
    """One day's reconciliation result for a single population (e.g. Phase 1
    FAST-vs-SAP as a whole, or -- once built -- one Phase 2 Flow Code).
    """

    recon_date: date
    population: str  # e.g. "Phase 1 - FAST vs SAP", or a Flow Code like "+301"
    source_a_label: str  # e.g. "SAP"
    source_a_total: float
    source_b_label: str  # e.g. "Cadency"
    source_b_total: float
    status: ReconStatus
    note: str = ""  # why a difference is expected, when the inputs themselves explain it
    difference: float = field(init=False)

    def __post_init__(self):
        self.difference = round(self.source_a_total - self.source_b_total, 2)


def daily_results_to_dataframe(daily_results: list[DailyResult]) -> pd.DataFrame:
    """Shared rendering for any list of DailyResult, regardless of phase.
    The Note column only appears when at least one result carries a note."""
    df = pd.DataFrame(
        [
            {
                "Date": r.recon_date,
                "Population": r.population,
                r.source_a_label: r.source_a_total,
                r.source_b_label: r.source_b_total,
                "Difference": r.difference,
                "Status": r.status.value,
                "Note": r.note,
            }
            for r in daily_results
        ]
    )
    if df.empty or not df["Note"].astype(bool).any():
        df = df.drop(columns="Note", errors="ignore")
    return df


@dataclass
class Phase1Result:
    account_number: str
    daily_results: list[DailyResult]
    sap_detail: pd.DataFrame  # filtered qualifying SAP rows, for drill-down
    cadency_detail: pd.DataFrame  # filtered qualifying Cadency rows, for drill-down

    def as_dataframe(self) -> pd.DataFrame:
        return daily_results_to_dataframe(self.daily_results)


@dataclass
class Phase2Result:
    account_number: str
    daily_results: list[DailyResult]  # one entry per (Flow Code, date)
    bank_detail: pd.DataFrame  # qualifying bank rows, tagged with "Flow Code", for drill-down
    cadency_detail: pd.DataFrame  # qualifying Cadency rows, tagged with "Flow Code", for drill-down

    def as_dataframe(self) -> pd.DataFrame:
        return daily_results_to_dataframe(self.daily_results)


# Phase 3 research findings, by kind. Only TIMING is not an exception.
FINDING_TIMING = "Timing"
FINDING_NO_BANK_RECEIPT = "No bank receipt"
FINDING_NOT_IN_CADENCY = "Bank line not in Cadency"
FINDING_UNEXPLAINED = "Unexplained"
FINDING_DCU_NOT_APPLIED = "DCU split not applied"
# Findings whose amount is a known, itemised part of the month's difference.
EXPLAINING_FINDINGS = (FINDING_NO_BANK_RECEIPT, FINDING_NOT_IN_CADENCY)


@dataclass(frozen=True)
class Phase3Finding:
    """One line of Phase 3's research: a timing tie, or an item to look into."""

    kind: str  # one of the FINDING_* constants
    first_date: date
    last_date: date
    amount: float  # effect on Bank - Cadency; 0 where it doesn't move the difference (timing, DCU)
    detail: str

    @property
    def is_exception(self) -> bool:
        return self.kind != FINDING_TIMING


@dataclass
class Phase3Result:
    account_number: str
    flow_code: str  # e.g. "+166"
    daily_results: list[DailyResult]  # one per date: bank vs. Cadency net of DCU splits, zero tolerance
    cadency_detail: pd.DataFrame  # qualifying reclaims, with DCU Split / Expected in account / Bank Tie
    bank_detail: pd.DataFrame  # qualifying bank lines, with Ties To
    dcu_detail: pd.DataFrame  # every DCU row, with what was done with it
    findings: list[Phase3Finding]
    cadency_full_total: float  # reclaims at the full amount Cadency books
    expected_total: float  # net of DCU splits -- what this account's bank should receive
    bank_total: float
    days_same_day: int  # Cadency post days that tie on their own day
    days_timing: int  # ... that tie once bank lines from a neighbouring day count
    days_with_exceptions: int  # ... that tie only with a reclaim set aside, or don't tie at all

    @property
    def dcu_split_total(self) -> float:
        return round(self.cadency_full_total - self.expected_total, 2)

    @property
    def difference(self) -> float:
        return round(self.bank_total - self.expected_total, 2)

    @property
    def exceptions(self) -> list[Phase3Finding]:
        return [f for f in self.findings if f.is_exception]

    @property
    def explained(self) -> float:
        return round(sum(f.amount for f in self.findings if f.kind in EXPLAINING_FINDINGS), 2)

    @property
    def unexplained(self) -> float:
        return round(self.difference - self.explained, 2)

    def dcu_status_counts(self) -> dict[str, int]:
        """'applied' / 'ignored' (another account's row) / 'not_applied'."""
        statuses = self.dcu_detail["Status"] if "Status" in self.dcu_detail else pd.Series(dtype=str)
        applied = int((statuses == "Applied").sum())
        ignored = int(statuses.str.startswith("Ignored").sum())
        return {"applied": applied, "ignored": ignored, "not_applied": len(statuses) - applied - ignored}

    def as_dataframe(self) -> pd.DataFrame:
        return daily_results_to_dataframe(self.daily_results)

    def findings_dataframe(self, exceptions: bool) -> pd.DataFrame:
        rows = [f for f in self.findings if f.is_exception == exceptions]
        return pd.DataFrame(
            [
                {
                    "Finding": f.kind,
                    "From": f.first_date,
                    "To": f.last_date,
                    "Effect on difference": f.amount,
                    "Detail": f.detail,
                }
                for f in rows
            ],
            columns=["Finding", "From", "To", "Effect on difference", "Detail"],
        )
