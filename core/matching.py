"""
Reconciliation matching logic.

Phase 1 and Phase 2 are fully built. Phase 3 is intentionally stubbed for
this shell -- see run_phase3 below.

Every function here takes an AccountConfig rather than hardcoding account
19803075 or "FAST" directly, so this module doesn't need to change to
onboard another account -- only core/config.py does.
"""

from __future__ import annotations

import pandas as pd

from .config import AccountConfig
from .models import DailyResult, Phase1Result, Phase2Result, ReconStatus
from .schema import resolve_bank_columns, resolve_sap_columns, resolve_trans_type_column


def run_phase1(
    cadency_df: pd.DataFrame,
    sap_df: pd.DataFrame,
    account: AccountConfig,
) -> Phase1Result:
    """Phase 1: FAST accounting activity vs. SAP.

    Population level, no tolerance for a difference. Per the business
    requirements doc: sum all qualifying SAP activity for a day, sum all
    qualifying Cadency activity for the same day, and the two totals must
    match exactly.

    Cadency qualifying rows: Reference 10 == account.fast_reference10_value
        AND trans-type code in account.phase1_trans_type_codes.
        (Date basis: Post Date.)
    SAP qualifying rows: Text field in account.phase1_sap_text_values.
        (Date basis: Document Date.)
    """
    trans_type_col = resolve_trans_type_column(cadency_df)
    sap_cols = resolve_sap_columns(sap_df)

    cadency_qualifying = cadency_df[
        (cadency_df["Reference 10"] == account.fast_reference10_value)
        & (cadency_df[trans_type_col].astype(str).isin(account.phase1_trans_type_codes))
    ].copy()
    cadency_qualifying["Post Date"] = pd.to_datetime(cadency_qualifying["Post Date"]).dt.date

    sap_qualifying = sap_df[sap_df[sap_cols["text"]].isin(account.phase1_sap_text_values)].copy()
    sap_qualifying["_date"] = pd.to_datetime(sap_qualifying[sap_cols["date"]]).dt.date

    cadency_daily = cadency_qualifying.groupby("Post Date")["Amount"].sum().rename("cadency_total")
    sap_daily = sap_qualifying.groupby("_date")[sap_cols["amount"]].sum().rename("sap_total")

    combined = pd.concat([sap_daily, cadency_daily], axis=1).fillna(0.0).sort_index()

    daily_results = []
    for recon_date, row in combined.iterrows():
        sap_total = round(float(row["sap_total"]), 2)
        cadency_total = round(float(row["cadency_total"]), 2)
        status = ReconStatus.RECONCILED if sap_total == cadency_total else ReconStatus.DOES_NOT_RECONCILE
        daily_results.append(
            DailyResult(
                recon_date=recon_date,
                population="Phase 1 - FAST vs SAP",
                source_a_label="SAP",
                source_a_total=sap_total,
                source_b_label="Cadency",
                source_b_total=cadency_total,
                status=status,
            )
        )

    return Phase1Result(
        account_number=account.account_number,
        daily_results=daily_results,
        sap_detail=sap_qualifying,
        cadency_detail=cadency_qualifying,
    )


def run_phase2(
    cadency_df: pd.DataFrame,
    bank_df: pd.DataFrame,
    account: AccountConfig,
) -> Phase2Result:
    """Phase 2: Standard Cash Activity vs. Bank Statement.

    Each bank Flow Code (account.flow_code_rules where phase == 2)
    reconciles independently, daily, against its own Cadency population --
    a failed Flow Code on a given day doesn't affect any other Flow Code's
    result for that day. No tolerance for a difference, except Flow Codes
    flagged manual_review (currently -495 / +195, since FAST doesn't yet
    generate WIRE / INCO transactions natively): those are always reported
    as MANUAL REVIEW rather than judged RECONCILED / DOES NOT RECONCILE.

    Cadency qualifying rows per Flow Code: Reference 10 == rule.cadency_ref10
        AND trans-type code == rule.cadency_trans_type_code, further
        narrowed by Reference 7 when the rule specifies it (see
        FlowCodeRule -- this is how the GDS/5801 population splits between
        -466 EFT and the +GDSCK_C/+GDSCK_S/-GDSCK_I check sub-statuses).
        Date basis: Effective Date for -466 (settlement-delay exception),
        Post Date otherwise.
    Bank qualifying rows: Flow Code column == rule.flow_code.
        (Date basis: whichever date column resolve_bank_columns finds.)
    """
    trans_type_col = resolve_trans_type_column(cadency_df)
    bank_cols = resolve_bank_columns(bank_df)

    cadency_df = cadency_df.copy()
    cadency_df["Post Date"] = pd.to_datetime(cadency_df["Post Date"]).dt.date
    if "Effective Date" in cadency_df.columns:
        cadency_df["Effective Date"] = pd.to_datetime(cadency_df["Effective Date"]).dt.date
    if "Reference 7" not in cadency_df.columns:
        cadency_df["Reference 7"] = ""
    cadency_df["Reference 7"] = cadency_df["Reference 7"].fillna("").astype(str)

    bank_df = bank_df.copy()
    bank_df["_date"] = pd.to_datetime(bank_df[bank_cols["date"]]).dt.date

    daily_results: list[DailyResult] = []
    cadency_detail_frames = []
    bank_detail_frames = []

    for rule in account.flow_code_rules:
        if rule.phase != 2:
            continue

        mask = (cadency_df["Reference 10"] == rule.cadency_ref10) & (
            cadency_df[trans_type_col].astype(str) == rule.cadency_trans_type_code
        )
        if rule.reference7_equals is not None:
            mask &= cadency_df["Reference 7"] == rule.reference7_equals

        cadency_qualifying = cadency_df[mask].copy()
        cadency_qualifying["Flow Code"] = rule.flow_code
        date_col = "Effective Date" if rule.use_effective_date else "Post Date"
        cadency_qualifying["_date"] = cadency_qualifying[date_col]

        bank_qualifying = bank_df[bank_df[bank_cols["flow_code"]] == rule.flow_code].copy()
        bank_qualifying["Flow Code"] = rule.flow_code

        cadency_daily = cadency_qualifying.groupby("_date")["Amount"].sum().rename("cadency_total")
        bank_daily = bank_qualifying.groupby("_date")[bank_cols["amount"]].sum().rename("bank_total")

        combined = pd.concat([bank_daily, cadency_daily], axis=1).fillna(0.0).sort_index()

        for recon_date, row in combined.iterrows():
            bank_total = round(float(row["bank_total"]), 2)
            cadency_total = round(float(row["cadency_total"]), 2)
            if rule.manual_review:
                status = ReconStatus.MANUAL_REVIEW
            elif bank_total == cadency_total:
                status = ReconStatus.RECONCILED
            else:
                status = ReconStatus.DOES_NOT_RECONCILE
            daily_results.append(
                DailyResult(
                    recon_date=recon_date,
                    population=f"Phase 2 - {rule.flow_code}",
                    source_a_label="Bank",
                    source_a_total=bank_total,
                    source_b_label="Cadency",
                    source_b_total=cadency_total,
                    status=status,
                )
            )

        cadency_detail_frames.append(cadency_qualifying)
        bank_detail_frames.append(bank_qualifying)

    cadency_detail = (
        pd.concat(cadency_detail_frames, ignore_index=True) if cadency_detail_frames else cadency_df.iloc[0:0]
    )
    bank_detail = pd.concat(bank_detail_frames, ignore_index=True) if bank_detail_frames else bank_df.iloc[0:0]

    return Phase2Result(
        account_number=account.account_number,
        daily_results=daily_results,
        bank_detail=bank_detail,
        cadency_detail=cadency_detail,
    )


# ---------------------------------------------------------------------------
# Phase 3 (Reclaim Credit/Debit netting against legacy Accounts 187/147) is
# intentionally stubbed. AccountConfig.legacy_account_187/147 fields already
# exist (see core/config.py) so this can be built without changing the
# config shape. Per the Business Requirements doc, Account 147 already has
# its own large, separate reconciliation process -- Phase 3 should consume a
# manually-provided extract of the RCCR/RCDB-attributable slice of that
# activity, not reproduce it.
# ---------------------------------------------------------------------------


def run_phase3(*args, **kwargs):
    raise NotImplementedError(
        "Phase 3 (Reclaim Credit/Debit netting against legacy Accounts 187/147) "
        "is not built yet."
    )
