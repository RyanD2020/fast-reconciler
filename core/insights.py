"""
Summaries of a reconciliation run, for the verdict banner, KPI tiles and the
"Run details" panel. Streamlit-free so it's unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from .config import AccountConfig
from .models import DailyResult, Phase1Result, Phase2Result, ReconStatus
from .schema import (
    normalize_bank_export,
    resolve_bank_columns,
    resolve_cadency_amount_column,
    resolve_sap_columns,
    resolve_trans_type_column,
)


@dataclass(frozen=True)
class ReconSummary:
    total: int
    reconciled: int
    not_reconciled: int
    manual_review: int
    net_difference: float  # over judged rows only -- manual-review rows aren't judged
    gross_difference: float  # sum of |difference| over judged rows
    worst: DailyResult | None  # largest |difference| among rows that don't reconcile
    first_date: date | None
    last_date: date | None
    distinct_days: int

    @property
    def judged(self) -> int:
        return self.reconciled + self.not_reconciled

    @property
    def all_clear(self) -> bool:
        return self.total > 0 and self.not_reconciled == 0


def summarize(daily_results: list[DailyResult]) -> ReconSummary:
    judged = [r for r in daily_results if r.status != ReconStatus.MANUAL_REVIEW]
    failing = [r for r in judged if r.status == ReconStatus.DOES_NOT_RECONCILE]
    dates = sorted({r.recon_date for r in daily_results})
    return ReconSummary(
        total=len(daily_results),
        reconciled=sum(r.status == ReconStatus.RECONCILED for r in daily_results),
        not_reconciled=len(failing),
        manual_review=sum(r.status == ReconStatus.MANUAL_REVIEW for r in daily_results),
        net_difference=round(sum(r.difference for r in judged), 2),
        gross_difference=round(sum(abs(r.difference) for r in judged), 2),
        worst=max(failing, key=lambda r: abs(r.difference)) if failing else None,
        first_date=dates[0] if dates else None,
        last_date=dates[-1] if dates else None,
        distinct_days=len(dates),
    )


def flow_code_of(result: DailyResult) -> str:
    return result.population.removeprefix("Phase 2 - ")


def _rows(loaded: pd.DataFrame, qualifying: pd.DataFrame) -> str:
    return f"{len(loaded):,} loaded, {len(qualifying):,} qualifying"


def _amount_label(cadency_df: pd.DataFrame) -> str:
    col = resolve_cadency_amount_column(cadency_df)
    return col if col != "Amount" else "Amount (unsigned fallback - no TA / True Amount column)"


def phase1_run_facts(
    cadency_df: pd.DataFrame, sap_df: pd.DataFrame, account: AccountConfig, result: Phase1Result
) -> list[tuple[str, str]]:
    """What the run actually used -- which columns resolved, which sign
    convention, how many rows survived the rules. Shown so a surprising
    total can be traced without opening the code (the 2026-10-20 sign bug
    would have been obvious from the "Cadency amount column" line alone).
    """
    sap_cols = resolve_sap_columns(sap_df)
    return [
        ("Cadency trans-type column", resolve_trans_type_column(cadency_df)),
        ("Cadency amount column", _amount_label(cadency_df)),
        (
            "Sign convention",
            "Cadency flipped to SAP's sign" if account.phase1_cadency_sign_flip else "As exported",
        ),
        ("SAP columns", f"{sap_cols['text']} / {sap_cols['date']} / {sap_cols['amount']}"),
        ("Cadency rows", _rows(cadency_df, result.cadency_detail)),
        ("SAP rows", _rows(sap_df, result.sap_detail)),
        ("Tolerance", "None - exact match to the cent"),
    ]


def phase2_run_facts(
    cadency_df: pd.DataFrame, bank_df: pd.DataFrame, account: AccountConfig, result: Phase2Result
) -> list[tuple[str, str]]:
    bank_df = normalize_bank_export(bank_df)
    bank_cols = resolve_bank_columns(bank_df)
    active_rules = account.flow_code_rules
    return [
        ("Cadency trans-type column", resolve_trans_type_column(cadency_df)),
        ("Cadency amount column", _amount_label(cadency_df)),
        ("Sign convention", "As exported (Phase 2 sign relationship not yet confirmed)"),
        ("Bank columns", f"{bank_cols['flow_code']} / {bank_cols['date']} / {bank_cols['amount']}"),
        (
            "Flow codes configured",
            f"{len(active_rules)} ({sum(r.manual_review for r in active_rules)} manual review, "
            f"{sum(r.phase == 3 for r in active_rules)} reclaim - judged before Phase 3 netting)",
        ),
        ("Cadency rows", _rows(cadency_df, result.cadency_detail)),
        ("Bank rows", _rows(bank_df, result.bank_detail)),
    ]
