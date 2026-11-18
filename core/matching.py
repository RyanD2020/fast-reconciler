"""
Reconciliation matching logic.

Phase 1 and Phase 2 are fully built. Phase 3 is built for reclaim credits
(+166 / RCCR, net of DCU's Account 187 splits); reclaim debits (-468 / RCDB /
Account 147) are still to come -- see run_phase3 below.

Every function here takes an AccountConfig rather than hardcoding account
19803075 or "FAST" directly, so this module doesn't need to change to
onboard another account -- only core/config.py does.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import date, timedelta

import pandas as pd

from .config import AccountConfig, FlowCodeRule
from .models import (
    FINDING_DCU_NOT_APPLIED,
    FINDING_NO_BANK_RECEIPT,
    FINDING_NOT_IN_CADENCY,
    FINDING_TIMING,
    FINDING_UNEXPLAINED,
    DailyResult,
    Phase1Result,
    Phase2Result,
    Phase3Finding,
    Phase3Result,
    ReconStatus,
)
from .schema import (
    flow_code_text,
    normalize_bank_export,
    normalize_code,
    resolve_bank_columns,
    resolve_cadency_amount_column,
    resolve_dcu_columns,
    resolve_sap_columns,
    resolve_trans_type_column,
)
from .timing import Allocation, Entry, Tie, allocate


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
        (Date basis: Post Date. Amount basis: the correctly-signed "TA" /
        "True Amount" column, not the unsigned "Amount" column -- see
        schema.py's docstring item 3 -- optionally sign-flipped per
        account.phase1_cadency_sign_flip, since Cadency and SAP were
        confirmed to record this population with opposite debit/credit
        conventions for the same activity.)
    SAP qualifying rows: Text field in account.phase1_sap_text_values.
        (Date basis: Document Date.)
    """
    trans_type_col = resolve_trans_type_column(cadency_df)
    cadency_amount_col = resolve_cadency_amount_column(cadency_df)
    sap_cols = resolve_sap_columns(sap_df)

    cadency_qualifying = cadency_df[
        (cadency_df["Reference 10"] == account.fast_reference10_value)
        & (normalize_code(cadency_df[trans_type_col]).isin(account.phase1_trans_type_codes))
    ].copy()
    cadency_qualifying["Post Date"] = pd.to_datetime(cadency_qualifying["Post Date"]).dt.date
    sign = -1.0 if account.phase1_cadency_sign_flip else 1.0
    cadency_qualifying["Phase 1 Amount"] = sign * cadency_qualifying[cadency_amount_col]

    sap_qualifying = sap_df[sap_df[sap_cols["text"]].isin(account.phase1_sap_text_values)].copy()
    sap_qualifying["_date"] = pd.to_datetime(sap_qualifying[sap_cols["date"]]).dt.date

    cadency_daily = cadency_qualifying.groupby("Post Date")["Phase 1 Amount"].sum().rename("cadency_total")
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

    Each bank Flow Code (every rule in account.flow_code_rules) reconciles
    independently, daily, against its own Cadency population --
    a failed Flow Code on a given day doesn't affect any other Flow Code's
    result for that day. No tolerance for a difference, except Flow Codes
    flagged manual_review (currently -495 / +195, since FAST doesn't yet
    generate WIRE / INCO transactions natively): those are always reported
    as MANUAL REVIEW rather than judged RECONCILED / DOES NOT RECONCILE.
    Phase 3 reclaim codes (+166 / -468) are judged directly, before any
    legacy-account netting, so they show up as exceptions instead of
    silently vanishing from the bank side (see FlowCodeRule).

    Cadency qualifying rows per Flow Code: Reference 10 == rule.cadency_ref10
        AND trans-type code in rule.cadency_trans_type_codes, further
        narrowed by Reference 7 when the rule specifies it (see
        FlowCodeRule -- this is how the GDS/5801 population splits between
        -466 EFT and the +GDSCK_C/+GDSCK_S/-GDSCK_I check sub-statuses).
        Date basis: Effective Date for -466 (settlement-delay exception),
        Post Date otherwise.
    Bank qualifying rows: Flow Code column == rule.flow_code.
        (Date basis: whichever date column resolve_bank_columns finds.)

    A day that doesn't reconcile gets a note when the inputs themselves
    explain the difference -- see _phase2_note. The status is still judged
    with zero tolerance; the note only says why.

    Uses the same correctly-signed Cadency amount column as Phase 1 ("TA" /
    "True Amount", not unsigned "Amount" -- see schema.py docstring item 3).
    No sign flip is applied here yet, unlike Phase 1: that flip was
    confirmed against real Phase 1 data specifically, and there's no
    equivalent confirmation yet for the Phase 2 bank/Cadency relationship.
    Confirm against real Phase 2 data before assuming either direction.
    """
    bank_df = normalize_bank_export(bank_df)
    trans_type_col = resolve_trans_type_column(cadency_df)
    cadency_amount_col = resolve_cadency_amount_column(cadency_df)
    bank_cols = resolve_bank_columns(bank_df)

    cadency_df = cadency_df.copy()
    cadency_df["_trans_type"] = normalize_code(cadency_df[trans_type_col])
    cadency_df["Post Date"] = pd.to_datetime(cadency_df["Post Date"]).dt.date
    if "Effective Date" in cadency_df.columns:
        cadency_df["Effective Date"] = pd.to_datetime(cadency_df["Effective Date"]).dt.date
    if "Reference 7" not in cadency_df.columns:
        cadency_df["Reference 7"] = ""
    cadency_df["Reference 7"] = normalize_code(cadency_df["Reference 7"])

    bank_df = bank_df.copy()
    bank_df["_date"] = pd.to_datetime(bank_df[bank_cols["date"]]).dt.date
    bank_codes = bank_df[bank_cols["flow_code"]].map(flow_code_text)
    cadency_post_range = _date_range(cadency_df["Post Date"])
    bank_range = _date_range(bank_df["_date"])

    daily_results: list[DailyResult] = []
    cadency_detail_frames = []
    bank_detail_frames = []

    for rule in account.flow_code_rules:
        mask = (cadency_df["Reference 10"] == rule.cadency_ref10) & (
            cadency_df["_trans_type"].isin(rule.cadency_trans_type_codes)
        )
        if rule.reference7_equals is not None:
            mask &= cadency_df["Reference 7"] == rule.reference7_equals

        cadency_qualifying = cadency_df[mask].drop(columns="_trans_type")
        cadency_qualifying["Flow Code"] = rule.flow_code
        date_col = "Effective Date" if rule.use_effective_date else "Post Date"
        cadency_qualifying["_date"] = cadency_qualifying[date_col]
        settlement_lag = _settlement_lag_days(cadency_qualifying) if rule.use_effective_date else 0

        bank_qualifying = bank_df[bank_codes == rule.flow_code].copy()
        bank_qualifying["Flow Code"] = rule.flow_code

        cadency_daily = cadency_qualifying.groupby("_date")[cadency_amount_col].sum().rename("cadency_total")
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
            note = ""
            if status != ReconStatus.RECONCILED:
                note = _phase2_note(recon_date, rule, account, settlement_lag, cadency_post_range, bank_range)
            daily_results.append(
                DailyResult(
                    recon_date=recon_date,
                    population=f"Phase 2 - {rule.flow_code}",
                    source_a_label="Bank",
                    source_a_total=bank_total,
                    source_b_label="Cadency",
                    source_b_total=cadency_total,
                    status=status,
                    note=note,
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


def _date_range(dates: pd.Series) -> tuple[date, date] | None:
    dates = dates.dropna()
    return (dates.min(), dates.max()) if not dates.empty else None


def _settlement_lag_days(cadency_qualifying: pd.DataFrame) -> int:
    """Longest Post Date -> Effective Date gap among this flow code's rows,
    in days -- how far back a day's settling activity can have been posted.
    Measured from the file rather than configured, since no settlement
    window has been confirmed (9/1 test data: EFTs posted 9/1 settle 9/3).
    """
    lag = (
        pd.to_datetime(cadency_qualifying["Effective Date"]) - pd.to_datetime(cadency_qualifying["Post Date"])
    ).dt.days.max()
    return max(int(lag), 0) if pd.notna(lag) else 0


def _phase2_note(
    recon_date: date,
    rule: FlowCodeRule,
    account: AccountConfig,
    settlement_lag: int,
    cadency_post_range: tuple[date, date] | None,
    bank_range: tuple[date, date] | None,
) -> str:
    """Why a Phase 2 day can't be expected to tie, when the inputs say so:
    the day sits outside what one of the files covers, or it's a reclaim
    code that needs Phase 3's legacy-account netting first. Returns "" when
    nothing explains the difference -- that's a genuine break.
    """
    notes = []
    if bank_range and not bank_range[0] <= recon_date <= bank_range[1]:
        notes.append(f"Outside the Treasury file's dates ({_span(bank_range)}) - the bank side for this day wasn't loaded.")
    elif cadency_post_range:
        first_post = recon_date - timedelta(days=settlement_lag)
        if first_post < cadency_post_range[0] or recon_date > cadency_post_range[1]:
            if settlement_lag:
                notes.append(
                    f"Effective Date basis: activity settling this day posts up to {settlement_lag} days earlier, "
                    f"but the Cadency file only covers post dates {_span(cadency_post_range)}."
                )
            else:
                notes.append(
                    f"Outside the Cadency file's post dates ({_span(cadency_post_range)}) - "
                    "the Cadency side for this day wasn't loaded."
                )
    if rule.phase == 3:
        legacy = (
            account.legacy_account_187
            if account.reclaim_credit_trans_type in rule.cadency_trans_type_codes
            else account.legacy_account_147
        )
        notes.append(f"Reclaim - judged before Phase 3 nets it against legacy Account {legacy}; a difference is expected until then.")
    return " ".join(notes)


def _span(dates: tuple[date, date]) -> str:
    first, last = dates
    return f"{first:%m/%d/%Y}" if first == last else f"{first:%m/%d/%Y} - {last:%m/%d/%Y}"


# ---------------------------------------------------------------------------
# Phase 3: Reclaim Credits net of DCU splits vs. the bank
# ---------------------------------------------------------------------------

DCU_APPLIED = "Applied"


def run_phase3(
    cadency_df: pd.DataFrame,
    bank_df: pd.DataFrame,
    dcu_df: pd.DataFrame,
    account: AccountConfig,
) -> Phase3Result:
    """Phase 3: Reclaim Credits (+166 / RCCR), net of DCU's splits, vs. the bank.

    Per Sean (2026-11-18): when reclaim funds are split between accounts,
    Cadency books the entire reclaim to this account and the other
    account's share (Account 187) is moved at month end -- so Cadency can
    carry more than this account's bank ever receives. DCU's reclaims sheet
    says how much of which reclaim went elsewhere. His example: Cadency
    books a reclaim in full, DCU says part of it was split off, so the bank
    should only see the rest.

    1. Cadency qualifying rows: the +166 rule's Reference 10 / trans-type
       codes (FAST / RCCR), at the full signed amount (TA / True Amount),
       dated by Post Date.
    2. DCU rows for THIS account (the Acct# column) are matched to one
       reclaim and subtracted from it -- see _apply_dcu_splits. Rows for any
       other account (e.g. 19803095) are ignored, per Sean.
    3. Bank qualifying rows: Flow Code == the rule's flow code (+166).
    4. Each day: bank total vs. Cadency total net of DCU splits, zero
       tolerance -- the same judgement as Phases 1 and 2.
    5. Timing research (core/timing.py) explains the days that don't tie --
       bank batches routinely land a day either side of the Cadency post
       date -- and isolates what's left to research. It never changes a
       day's status; it writes the day's note and the findings list.

    The reclaim-debit side (-468 / RCDB / Account 147) isn't built: there's
    no test data for it yet.
    """
    rule = _reclaim_rule(account, account.reclaim_credit_trans_type)
    bank_df = normalize_bank_export(bank_df)
    trans_type_col = resolve_trans_type_column(cadency_df)
    amount_col = resolve_cadency_amount_column(cadency_df)
    bank_cols = resolve_bank_columns(bank_df)
    dcu_cols = resolve_dcu_columns(dcu_df)
    expected_col = f"Expected in {account.account_number}"

    reclaims = cadency_df[
        (cadency_df["Reference 10"] == rule.cadency_ref10)
        & (normalize_code(cadency_df[trans_type_col]).isin(rule.cadency_trans_type_codes))
    ].copy()
    reclaims["Post Date"] = pd.to_datetime(reclaims["Post Date"]).dt.date
    full = pd.to_numeric(reclaims[amount_col], errors="coerce").fillna(0.0)
    split, dcu_detail = _apply_dcu_splits(reclaims, full, dcu_df, dcu_cols, account, expected_col)
    reclaims["DCU Split"] = split
    reclaims[expected_col] = (full - split).round(2)

    bank = bank_df[bank_df[bank_cols["flow_code"]].map(flow_code_text) == rule.flow_code].copy()
    bank_days = pd.to_datetime(bank[bank_cols["date"]]).dt.date
    bank_amounts = pd.to_numeric(bank[bank_cols["amount"]], errors="coerce").fillna(0.0)

    allocation = allocate(
        [Entry(k, d, _cents(a)) for k, d, a in zip(reclaims.index, reclaims["Post Date"], reclaims[expected_col])],
        [Entry(k, d, _cents(a)) for k, d, a in zip(bank.index, bank_days, bank_amounts)],
        window=account.phase3_timing_window_days,
    )
    cadency_daily = reclaims.groupby("Post Date")[expected_col].sum().rename("cadency")
    context = _ResearchContext(
        reclaims=reclaims,
        expected_by_day={d: _cents(v) for d, v in cadency_daily.items()},
        cadency_range=_date_range(reclaims["Post Date"]),
        bank_range=_date_range(bank_days),
        window=account.phase3_timing_window_days,
    )
    notes = _phase3_notes(allocation, context)

    bank_daily = bank_amounts.groupby(bank_days).sum().rename("bank")
    combined = pd.concat([bank_daily, cadency_daily], axis=1).fillna(0.0).sort_index()
    daily_results = []
    for recon_date, row in combined.iterrows():
        bank_total = round(float(row["bank"]), 2)
        cadency_total = round(float(row["cadency"]), 2)
        status = ReconStatus.RECONCILED if bank_total == cadency_total else ReconStatus.DOES_NOT_RECONCILE
        daily_results.append(
            DailyResult(
                recon_date=recon_date,
                population=f"Phase 3 - {rule.flow_code}",
                source_a_label="Bank",
                source_a_total=bank_total,
                source_b_label="Cadency net of DCU",
                source_b_total=cadency_total,
                status=status,
                note="" if status == ReconStatus.RECONCILED else notes.get(recon_date, ""),
            )
        )

    reclaims["Bank Tie"] = _reclaim_tie_labels(allocation, reclaims["Post Date"])
    bank["Ties To"] = _bank_tie_labels(allocation, bank.index)

    def days_in(groups) -> set[date]:
        return {d for g in groups for d in g.days}

    return Phase3Result(
        account_number=account.account_number,
        flow_code=rule.flow_code,
        daily_results=daily_results,
        cadency_detail=reclaims,
        bank_detail=bank,
        dcu_detail=dcu_detail,
        findings=_phase3_findings(allocation, dcu_detail, dcu_cols, context),
        cadency_full_total=round(float(full.sum()), 2),
        expected_total=round(float(reclaims[expected_col].sum()), 2),
        bank_total=round(float(bank_amounts.sum()), 2),
        days_same_day=len(days_in(allocation.same_day_ties())),
        days_timing=len(days_in(allocation.timing_ties())),
        days_with_exceptions=len(days_in(allocation.set_aside_ties()) | days_in(allocation.unexplained)),
    )


def _reclaim_rule(account: AccountConfig, trans_type: str) -> FlowCodeRule:
    for rule in account.flow_code_rules:
        if rule.phase == 3 and trans_type in rule.cadency_trans_type_codes:
            return rule
    raise ValueError(f"Account {account.account_number} has no Phase 3 flow-code rule for {trans_type}.")


def _cents(amount) -> int:
    return int(round(float(amount) * 100))


def _money(cents: int) -> str:
    return f"{'-' if cents < 0 else ''}${abs(cents) / 100:,.2f}"


def _code(value) -> str:
    """One identifier as clean text -- 900001234.0 -> "900001234". The
    scalar twin of schema.normalize_code."""
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    return str(value).strip().removesuffix(".0")


def _digits(value) -> str:
    """Contract numbers compared on their digits: "GA01234" and 1234 match."""
    return re.sub(r"\D", "", _code(value)).lstrip("0")


def _apply_dcu_splits(
    reclaims: pd.DataFrame,
    full: pd.Series,
    dcu_df: pd.DataFrame,
    cols: dict,
    account: AccountConfig,
    expected_col: str,
) -> tuple[pd.Series, pd.DataFrame]:
    """How much of each reclaim DCU says went to another account, and the DCU
    sheet annotated with what was done with each row.

    A DCU row is matched on Certificate Number = Cadency Reference 4, confirmed
    by Contract Number = the digits of Reference 2 ("GA01234" <-> 1234) --
    the pairing in Sean's 2026-11-18 example. If several reclaims still
    match, the one posted on the DCU row's Effective Date wins (in the test
    data, DCU's Effective Date is the Cadency Post Date). A row is NOT
    applied -- and becomes a finding -- when it has no account, amount or
    certificate, matches no reclaim, matches on certificate but not
    contract, stays ambiguous, or would split off more than the reclaim
    is worth. Applying a split to the wrong reclaim would silently move a
    real difference somewhere else, so every doubt goes to a human.

    The DCU amount is an absolute value; it reduces the reclaim's magnitude.
    """
    dcu = dcu_df.dropna(how="all").copy()
    certificates = (
        normalize_code(reclaims["Reference 4"]) if "Reference 4" in reclaims else pd.Series("", index=reclaims.index)
    )
    contracts = reclaims["Reference 2"].map(_digits) if "Reference 2" in reclaims else pd.Series("", index=reclaims.index)
    amounts = pd.to_numeric(dcu[cols["amount"]], errors="coerce").abs()

    statuses, matches = [], []
    for (_, row), amount in zip(dcu.iterrows(), amounts):
        status, key = _match_dcu_row(row, amount, cols, account, certificates, contracts, reclaims["Post Date"])
        statuses.append(status)
        matches.append(key)

    split = pd.Series(0.0, index=reclaims.index)
    for key, amount in zip(matches, amounts):
        if key is not None:
            split[key] += amount
    over = {key for key in matches if key is not None and round(split[key], 2) > round(abs(full[key]), 2)}
    for i, key in enumerate(matches):
        if key in over:
            statuses[i] = "Not applied - splits add up to more than the reclaim"
            matches[i] = None
    split[list(over)] = 0.0
    split = split.where(full >= 0, -split).round(2)

    dcu["Status"] = pd.Series(statuses, index=dcu.index, dtype=object)
    dcu["Cadency Post Date"] = [reclaims.at[k, "Post Date"] if k is not None else None for k in matches]
    dcu["Cadency Full Amount"] = [round(float(full[k]), 2) if k is not None else None for k in matches]
    dcu[expected_col] = [round(float(full[k] - split[k]), 2) if k is not None else None for k in matches]
    return split, dcu


def _match_dcu_row(row, amount, cols, account, certificates, contracts, post_dates) -> tuple[str, object]:
    acct = _code(row[cols["account"]]).lstrip("0")
    if not acct:
        return "Not applied - no account on the DCU row", None
    if acct != account.account_number.lstrip("0"):
        return f"Ignored - account {acct}", None
    if pd.isna(amount):
        return "Not applied - no amount", None
    certificate = _code(row[cols["certificate"]])
    if not certificate:
        return "Not applied - no certificate number", None
    candidates = list(certificates.index[certificates == certificate])
    if not candidates:
        return "Not applied - no Cadency reclaim with this certificate (Reference 4)", None
    contract = _digits(row[cols["contract"]]) if cols["contract"] else ""
    if contract:
        candidates = [k for k in candidates if contracts[k] == contract]
        if not candidates:
            return "Not applied - certificate matches a reclaim, but its contract (Reference 2) doesn't", None
    if len(candidates) > 1 and cols["effective_date"]:
        effective = pd.to_datetime(row[cols["effective_date"]], errors="coerce")
        on_day = [k for k in candidates if pd.notna(effective) and post_dates[k] == effective.date()]
        candidates = on_day or candidates
    if len(candidates) > 1:
        return f"Not applied - {len(candidates)} Cadency reclaims match; can't tell which", None
    return DCU_APPLIED, candidates[0]


class _ResearchContext:
    """What the notes and findings need to put a tie into words."""

    def __init__(self, reclaims, expected_by_day, cadency_range, bank_range, window):
        self.reclaims = reclaims
        self.expected_by_day = expected_by_day
        self.cadency_range = cadency_range
        self.bank_range = bank_range
        self.window = window

    def expected(self, days) -> int:
        return sum(self.expected_by_day.get(d, 0) for d in days)

    def describe(self, key) -> str:
        row = self.reclaims.loc[key]
        parts = []
        if "Reference 2" in row and _code(row["Reference 2"]):
            parts.append(f"contract {_code(row['Reference 2'])}")
        if "Reference 4" in row and _code(row["Reference 4"]):
            parts.append(f"certificate {_code(row['Reference 4'])}")
        return ", ".join(parts) or f"Cadency row {key}"

    def treasury_edge(self, days) -> str:
        """Why a missing receipt might just be outside the Treasury file."""
        if self.bank_range is None:
            return " The Treasury file has no lines for this flow code."
        if days[-1] >= self.bank_range[1]:
            return f" The Treasury file ends {self.bank_range[1]:%m/%d/%Y}, so a later receipt isn't loaded."
        if days[0] <= self.bank_range[0]:
            return f" The Treasury file starts {self.bank_range[0]:%m/%d/%Y}, so an earlier receipt isn't loaded."
        return ""

    def cadency_edge(self, day) -> str:
        """Why an unclaimed bank line might belong to reclaims outside the Cadency file."""
        if self.cadency_range is None:
            return " The Cadency file has no reclaims."
        if day <= self.cadency_range[0]:
            return f" The Cadency file starts {self.cadency_range[0]:%m/%d/%Y} - it may be for reclaims posted before that."
        if day >= self.cadency_range[1]:
            return f" The Cadency file ends {self.cadency_range[1]:%m/%d/%Y} - it may be for reclaims posted after that."
        return ""


def _days_text(days) -> str:
    return _span((days[0], days[-1]))


def _cents_by_day(lines) -> dict[date, int]:
    by_day: dict[date, int] = defaultdict(int)
    for line in lines:
        by_day[line.day] += line.cents
    return dict(sorted(by_day.items()))


def _lines_text(lines) -> str:
    """Bank lines summed per day: "09/01/2026 ($1,350.25) and 09/02/2026 ($75.10)"."""
    parts = [f"{d:%m/%d/%Y} ({_money(c)})" for d, c in _cents_by_day(lines).items()]
    if not parts:
        return "none"
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def _tie_sentence(tie: Tie, context: _ResearchContext) -> str:
    subject = "this day's reclaims" if len(tie.days) == 1 else f"reclaims posted {_days_text(tie.days)} together"
    lines = _lines_text(tie.lines)
    if tie.set_aside is None:
        return f"Timing: {subject} tie exactly to bank lines on {lines}."
    item = tie.set_aside
    posted = f" posted {item.day:%m/%d/%Y}" if len(tie.days) > 1 else ""
    return (
        f"{subject[0].upper()}{subject[1:]} tie exactly to bank lines on {lines} once the "
        f"{_money(item.cents)} reclaim{posted} ({context.describe(item.key)}) is set aside - "
        f"no bank receipt found for it.{context.treasury_edge(tie.days)}"
    )


def _phase3_notes(allocation: Allocation, context: _ResearchContext) -> dict[date, str]:
    """A note per date: first how its reclaims tie (the Cadency side), then
    whose reclaims its bank lines are (the bank side). Shown only on days
    that don't reconcile, like Phase 2's notes."""
    sentences: dict[date, list[str]] = defaultdict(list)
    for tie in allocation.ties:
        if tie.is_timing or tie.set_aside is not None:
            for d in tie.days:
                sentences[d].append(_tie_sentence(tie, context))
    for group in allocation.unexplained:
        too_many = "" if group.searched else " Too many bank lines nearby to search."
        for d in group.days:
            sentences[d].append(
                f"No exact tie with bank lines within {context.window} activity day(s) either side - research needed."
                f"{too_many}{context.treasury_edge(group.days)}"
            )

    for tie in allocation.ties:
        moved = _cents_by_day(line for line in tie.lines if line.day not in tie.days)
        for d, cents in moved.items():
            sentences[d].append(f"{_money(cents)} of this day's bank activity belongs to reclaims posted {_days_text(tie.days)}.")
    for group in allocation.unexplained:
        nearby = _cents_by_day(line for line in group.lines if line.day not in group.days)
        for d, cents in nearby.items():
            sentences[d].append(
                f"{_money(cents)} of this day's bank activity is unclaimed, near the unexplained reclaims "
                f"posted {_days_text(group.days)}."
            )
    for line in allocation.unclaimed:
        sentences[line.day].append(
            f"{_money(line.cents)} of this day's bank activity matches no Cadency reclaim.{context.cadency_edge(line.day)}"
        )
    return {d: " ".join(s) for d, s in sentences.items()}


def _phase3_findings(
    allocation: Allocation, dcu_detail: pd.DataFrame, dcu_cols: dict, context: _ResearchContext
) -> list[Phase3Finding]:
    findings = []
    for tie in allocation.timing_ties():
        findings.append(
            Phase3Finding(
                FINDING_TIMING, tie.days[0], tie.days[-1], 0.0,
                f"Cadency {_money(context.expected(tie.days))} net of DCU ties exactly to bank lines on "
                f"{_lines_text(tie.lines)}.",
            )
        )
    for tie in allocation.set_aside_ties():
        item = tie.set_aside
        findings.append(
            Phase3Finding(
                FINDING_NO_BANK_RECEIPT, item.day, item.day, -item.cents / 100,
                f"{_money(item.cents)} reclaim posted {item.day:%m/%d/%Y} ({context.describe(item.key)}) has no bank "
                f"receipt: {_days_text(tie.days)} ties exactly to bank lines on {_lines_text(tie.lines)} without it."
                f"{context.treasury_edge(tie.days)}",
            )
        )
    for group in allocation.unexplained:
        expected = context.expected(group.days)
        nearby = sum(line.cents for line in group.lines)
        too_many = "" if group.searched else " Too many bank lines nearby to search."
        findings.append(
            Phase3Finding(
                FINDING_UNEXPLAINED, group.days[0], group.days[-1], (nearby - expected) / 100,
                f"Cadency {_money(expected)} net of DCU; unclaimed bank lines nearby: {_lines_text(group.lines)}. "
                f"No combination ties exactly.{too_many}{context.treasury_edge(group.days)}",
            )
        )
    for line in allocation.unclaimed:
        findings.append(
            Phase3Finding(
                FINDING_NOT_IN_CADENCY, line.day, line.day, line.cents / 100,
                f"{_money(line.cents)} bank line on {line.day:%m/%d/%Y} - no Cadency reclaim accounts for it."
                f"{context.cadency_edge(line.day)}",
            )
        )
    for _, row in dcu_detail[dcu_detail["Status"].str.startswith("Not applied")].iterrows():
        effective = _dcu_effective_date(row, dcu_cols)
        reason = row["Status"].removeprefix("Not applied - ")
        findings.append(
            Phase3Finding(
                FINDING_DCU_NOT_APPLIED, effective, effective, 0.0,
                f"{reason[0].upper()}{reason[1:]}: {_dcu_row_text(row, dcu_cols)}. "
                "The reclaim's full amount is still expected in this account.",
            )
        )
    return sorted(findings, key=lambda f: (f.first_date or date.min, f.kind))


def _dcu_effective_date(row, cols) -> date | None:
    value = pd.to_datetime(row[cols["effective_date"]], errors="coerce") if cols["effective_date"] else pd.NaT
    return value.date() if pd.notna(value) else None


def _dcu_row_text(row, cols) -> str:
    parts = []
    if cols["contract"] and _code(row[cols["contract"]]):
        parts.append(f"contract {_code(row[cols['contract']])}")
    if _code(row[cols["certificate"]]):
        parts.append(f"certificate {_code(row[cols['certificate']])}")
    amount = pd.to_numeric(row[cols["amount"]], errors="coerce")
    if pd.notna(amount):
        parts.append(f"split {_money(_cents(abs(amount)))}")
    return "DCU row " + (", ".join(parts) if parts else "with no details")


def _reclaim_tie_labels(allocation: Allocation, post_dates: pd.Series) -> list[str]:
    """Per reclaim: how its day tied to the bank."""
    by_day: dict[date, str] = {}
    for tie in allocation.ties:
        bank_days = sorted({line.day for line in tie.lines})
        if tie.spans_days:
            label = "Timing - bank " + ", ".join(f"{d:%m/%d}" for d in bank_days)
        else:
            label = "Same day"
        for d in tie.days:
            by_day[d] = label
    for group in allocation.unexplained:
        for d in group.days:
            by_day[d] = "Unexplained"
    set_aside = {tie.set_aside.key for tie in allocation.set_aside_ties()}
    return ["No bank receipt" if key in set_aside else by_day.get(day, "") for key, day in post_dates.items()]


def _bank_tie_labels(allocation: Allocation, index) -> list[str]:
    """Per bank line: whose reclaims it pays for."""
    by_key: dict[object, str] = {}
    for tie in allocation.ties:
        for line in tie.lines:
            by_key[line.key] = f"Cadency {_days_text(tie.days)}"
    for group in allocation.unexplained:
        for line in group.lines:
            by_key[line.key] = f"Unexplained - near Cadency {_days_text(group.days)}"
    for line in allocation.unclaimed:
        by_key[line.key] = "No Cadency reclaim"
    return [by_key.get(key, "") for key in index]


