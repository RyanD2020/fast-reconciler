"""
Account configuration registry.

Each AccountConfig captures the business rules that are specific to one
reconciliation account (clearing account). The matching engine in
core/matching.py is written generically against these fields, so onboarding
another account -- e.g. PRT, PAR, or any of the ~20 accounts mentioned in the
CODA meeting notes as the long-term goal -- means adding a new AccountConfig
entry below, not rewriting matching logic.

Phase 1 fields are fully used today by core/matching.py. Phase 2
(flow_code_rules) and Phase 3 (legacy account fields) are captured now so the
config shape won't need to change when those phases are built -- but the
matching logic for them is still a stub. See core/matching.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class FlowCodeRule:
    """One bank-Flow-Code -> Cadency-population rule.

    phase 2 rules (Treasury/bank cash matching) are consumed by
    core.matching.run_phase2. phase 3 rules (+166/-468 reclaim netting
    against legacy Accounts 187/147) are still captured as data only --
    run_phase3 is a stub.

    reference7_equals / reference7_not_in exist because GDS/5801 activity
    covers more than one Flow Code: Reference 7 = C/S/I identifies GDS
    check cancel/stop/issue sub-status (the GDSCK_* codes), while -466 (the
    outgoing EFT population) is everything else in GDS/5801 -- i.e. GDS/5801
    rows whose Reference 7 is NOT one of the check sub-statuses.
    """

    flow_code: str
    cadency_ref10: str  # "FAST" or "GDS"
    cadency_trans_type_code: str  # expected value in the trans-type column, e.g. "CHKD", "BRCR", "5801"
    phase: int = 2
    use_effective_date: bool = False
    manual_review: bool = False
    reference7_equals: str | None = None
    reference7_not_in: tuple[str, ...] = ()
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

    # --- Phase 2: Treasury / bank Flow Code matching (stub) ---
    gds_reference10_value: str = "GDS"
    flow_code_rules: tuple[FlowCodeRule, ...] = ()

    # --- Phase 3: Reclaim Credit/Debit vs. legacy accounts (stub) ---
    reclaim_credit_trans_type: str = "RCCR"
    reclaim_debit_trans_type: str = "RCDB"
    legacy_account_187: str | None = "187"  # Reclaim Credit legacy account; conditional input per the CODA meeting notes
    legacy_account_147: str | None = "147"  # Reclaim Debit legacy account; conditional input per the CODA meeting notes


# Registry of configured accounts. Add a new AccountConfig(...) entry here to
# onboard another clearing account. No changes to core/matching.py should be
# required for Phase 1 to work against a new account.
ACCOUNTS: dict[str, AccountConfig] = {
    "19803075": AccountConfig(
        account_number="19803075",
        display_name="FAST Pension Annuity Clearing Account (19803075)",
        flow_code_rules=(
            FlowCodeRule("+301", "FAST", "CHKD", notes="Check deposits"),
            FlowCodeRule("-466", "GDS", "5801", use_effective_date=True,
                         reference7_not_in=("C", "S", "I"),
                         notes="Outgoing EFT - use Effective Date, not Post Date (settlement delay); "
                               "GDS/5801 minus the GDSCK check sub-statuses"),
            FlowCodeRule("+168", "FAST", "BRCR", notes="Bank return credits / returned EFT"),
            FlowCodeRule("+GDSCK_C", "GDS", "5801", reference7_equals="C", notes="Cancelled GDS check"),
            FlowCodeRule("+GDSCK_S", "GDS", "5801", reference7_equals="S", notes="Stopped GDS check"),
            FlowCodeRule("-GDSCK_I", "GDS", "5801", reference7_equals="I", notes="Issued GDS check"),
            FlowCodeRule("-495", "FAST", "WIRE", manual_review=True,
                         notes="Outgoing wire - manual Ad Hoc SJE until FAST generates WIRE transactions"),
            FlowCodeRule("+195", "FAST", "INCO", manual_review=True,
                         notes="Incoming wire - manual Ad Hoc SJE until FAST generates INCO transactions"),
            FlowCodeRule("+166", "FAST", "RCCR", phase=3,
                         notes="Reclaim Credit - net against Account 187 before validating"),
            FlowCodeRule("-468", "FAST", "RCDB", phase=3,
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
