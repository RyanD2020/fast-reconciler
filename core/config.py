"""
Account configuration registry.

Each AccountConfig captures the business rules that are specific to one
reconciliation account (clearing account). The matching engine in
core/matching.py is written generically against these fields, so onboarding
another account -- e.g. PRT, PAR, or any of the ~20 accounts mentioned in the
CODA meeting notes as the long-term goal -- means adding a new AccountConfig
entry below, not rewriting matching logic.

Phase 1 and Phase 2 fields are fully used by core/matching.py. Phase 3 uses
the reclaim-credit fields (+166 / RCCR / Account 187); the reclaim-debit side
(-468 / RCDB / Account 147) is captured but not built yet -- no test data for
it so far. See core/matching.py::run_phase3.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FlowCodeRule:
    """One bank-Flow-Code -> Cadency-population rule.

    Every rule is judged by core.matching.run_phase2, so every Flow Code
    on the bank statement gets a result. phase 3 rules (+166/-468 reclaim
    netting against legacy Accounts 187/147) are judged there directly,
    without the netting -- they're expected NOT to reconcile in Phase 2;
    Sean's 9/1 test data relies on +166 surfacing as an exception rather
    than disappearing. run_phase3 is where +166 is netted and researched.

    reference7_equals exists because GDS/5801 activity covers more than one
    Flow Code, each identified by its own Reference 7 tag (confirmed with
    Sean, 2026-09-23): "C"/"S"/"I" for the three GDSCK check sub-statuses,
    and "E" for EFT activity (-466). Each is a positive match on its own
    value -- there's no "everything else" rule.
    """

    flow_code: str
    cadency_ref10: str  # "FAST" or "GDS"
    cadency_trans_type_codes: tuple[str, ...]  # accepted values in the trans-type column, e.g. ("CHKD",), ("5801", "DEDU")
    phase: int = 2
    use_effective_date: bool = False
    manual_review: bool = False
    reference7_equals: str | None = None
    notes: str = ""


@dataclass(frozen=True)
class AccountConfig:
    account_number: str
    display_name: str

    # --- Phase 1: FAST accounting activity vs. SAP (built) ---
    fast_reference10_value: str = "FAST"
    phase1_trans_type_codes: tuple[str, ...] = ("5801", "2105", "DEDU", "OVER", "SJ90")
    phase1_sap_text_values: tuple[str, ...] = (
        "Annuity Payment",
        "Death Claim Disbursement",
        "Write Off",
        "Premium Remittance - Overpayment Recoupment",
    )
    # Confirmed 2026-10-20 against real data: Cadency's True Amount (TA) and
    # SAP's Amount in Local Currency record this Phase 1 population with
    # opposite signs for the same economic activity (two independent
    # systems, two different debit/credit conventions) -- flipping
    # Cadency's sign is what makes the daily totals match exactly. This is
    # recorded per-account rather than hardcoded in matching.py because
    # there's no evidence yet that every account's Phase 1 population will
    # need the same flip.
    phase1_cadency_sign_flip: bool = False

    # --- Phase 2: Treasury / bank Flow Code matching ---
    gds_reference10_value: str = "GDS"
    flow_code_rules: tuple[FlowCodeRule, ...] = ()

    # --- Phase 3: Reclaim Credit/Debit vs. legacy accounts ---
    reclaim_credit_trans_type: str = "RCCR"
    reclaim_debit_trans_type: str = "RCDB"
    # Reclaim Credit legacy account. Per Sean (2026-11-18): when reclaim
    # funds are split between accounts, Cadency books the full reclaim here
    # and the other account's share is moved at month end; DCU's reclaims
    # sheet says how much. That sheet is Phase 3's Account 187 input.
    legacy_account_187: str | None = "187"
    legacy_account_147: str | None = "147"  # Reclaim Debit legacy account; conditional input per the CODA meeting notes
    # How far a reclaim's bank receipt can sit from its Cadency post date, in
    # activity days (any date with a Cadency post or a bank line, so weekends
    # and holidays don't count). 1 fits all of Sean's September 2026 test
    # data -- not a confirmed business rule. See core/timing.py.
    phase3_timing_window_days: int = 1


# Registry of configured accounts. Add a new AccountConfig(...) entry here to
# onboard another clearing account. No changes to core/matching.py should be
# required for Phase 1 to work against a new account.
ACCOUNTS: dict[str, AccountConfig] = {
    "19803075": AccountConfig(
        account_number="19803075",
        display_name="FAST Pension Annuity Clearing Account (19803075)",
        phase1_cadency_sign_flip=True,
        flow_code_rules=(
            FlowCodeRule("+301", "FAST", ("CHKD",), notes="Check deposits"),
            FlowCodeRule("-466", "GDS", ("5801",), use_effective_date=True, reference7_equals="E",
                         notes="Outgoing EFT - use Effective Date, not Post Date (settlement delay); "
                               "EFT activity is tagged Reference 7 = E"),
            FlowCodeRule("+168", "FAST", ("BRCR",), notes="Bank return credits / returned EFT"),
            FlowCodeRule("+GDSCK_C", "GDS", ("5801",), reference7_equals="C", notes="Cancelled GDS check"),
            FlowCodeRule("+GDSCK_S", "GDS", ("5801",), reference7_equals="S", notes="Stopped GDS check"),
            FlowCodeRule("-GDSCK_I", "GDS", ("5801", "DEDU"), reference7_equals="I",
                         notes="Issued GDS check - GDS deduction checks (DEDU) are issued checks too; "
                               "9/1 Treasury -GDSCK_I only ties when they're included"),
            FlowCodeRule("-495", "FAST", ("WIRE",), manual_review=True,
                         notes="Outgoing wire - manual Ad Hoc SJE until FAST generates WIRE transactions"),
            FlowCodeRule("+195", "FAST", ("INCO",), manual_review=True,
                         notes="Incoming wire - manual Ad Hoc SJE until FAST generates INCO transactions"),
            FlowCodeRule("+166", "FAST", ("RCCR",), phase=3,
                         notes="Reclaim Credit - net of DCU's Account 187 splits before validating (Phase 3)"),
            FlowCodeRule("-468", "FAST", ("RCDB",), phase=3,
                         notes="Reclaim Debit - net against Account 147 before validating"),
        ),
    ),
    # Add the next account here, e.g.:
    # "XXXXXXXX": AccountConfig(
    #     account_number="XXXXXXXX",
    #     display_name="PRT Clearing Account (XXXXXXXX)",
    #     ...
    # ),
}


def get_account(account_number: str) -> AccountConfig:
    try:
        return ACCOUNTS[account_number]
    except KeyError as exc:
        raise KeyError(
            f"No AccountConfig registered for account {account_number!r}. "
            f"Known accounts: {list(ACCOUNTS)}"
        ) from exc
