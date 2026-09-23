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
    difference: float = field(init=False)

    def __post_init__(self):
        self.difference = round(self.source_a_total - self.source_b_total, 2)


def daily_results_to_dataframe(daily_results: list[DailyResult]) -> pd.DataFrame:
    """Shared rendering for any list of DailyResult, regardless of phase."""
    return pd.DataFrame(
        [
            {
                "Date": r.recon_date,
                "Population": r.population,
                r.source_a_label: r.source_a_total,
                r.source_b_label: r.source_b_total,
                "Difference": r.difference,
                "Status": r.status.value,
            }
            for r in daily_results
        ]
    )


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
