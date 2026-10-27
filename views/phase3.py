"""Phase 3 -- reclaim netting against legacy Accounts 187 / 147. Not built yet:
this page shows the rules already captured in config and what's still open."""

import pandas as pd
import streamlit as st

from core import components as c
from core.ui import current_account, render

account = current_account()
rules = {code: r for r in account.flow_code_rules if r.phase == 3 for code in r.cadency_trans_type_codes}

render(
    c.hero(
        title="Reclaim netting",
        eyebrow="Phase 3 · In design",
        lede=(
            "Cadency carries the full reclaim amount, but part of it belongs to legacy clearing accounts. "
            "Phase 3 nets that portion out before judging what belongs to this account."
        ),
        meta=[account.display_name, "Accounts 187 & 147", "Not built yet"],
    )
)

render(c.step("01", "Captured in config", "The pairings Phase 3 will net - already recorded, so the engine can be built without reshaping the config."))
left, right = st.columns(2, gap="large")
with left:
    credit = rules.get(account.reclaim_credit_trans_type)
    render(
        c.legacy_card(
            f"Legacy Account {account.legacy_account_187 or '-'}",
            credit.flow_code if credit else "+166",
            account.reclaim_credit_trans_type,
            "Reclaim credits",
            "Account 187 activity applies only to Reclaim Credits. A conditional input, not a daily one - "
            "when it's required still needs to be documented.",
        )
    )
with right:
    debit = rules.get(account.reclaim_debit_trans_type)
    render(
        c.legacy_card(
            f"Legacy Account {account.legacy_account_147 or '-'}",
            debit.flow_code if debit else "-468",
            account.reclaim_debit_trans_type,
            "Reclaim debits",
            "Account 147 activity applies only to Reclaim Debits. That account already has its own mature "
            "reconciliation - Phase 3 consumes a slice of it, it doesn't rebuild it.",
        )
    )

render(c.step("02", "Where everything stands"))
render(
    c.roadmap(
        [
            ("RECONCILED", "Phase 1 · FAST vs. SAP", "Live. Reconciles real August and September data to the cent."),
            ("RECONCILED", "Phase 2 · Treasury flow codes", "Built. The Cadency-vs-bank sign relationship still needs confirming on a real bank export."),
            (None, "Phase 3 · Reclaim netting", "In design. Waiting on the Account 187 trigger condition and a sample legacy extract."),
            (None, "Monthly final roundup", "Planned. A separate, secondary control - methodology still to be agreed."),
        ]
    )
)
render(c.callout("Open question for the business: when is Account 187 activity required as an input?", tone="info"))

with st.expander("Phase 3 flow-code rules in config"):
    st.dataframe(pd.DataFrame([r.__dict__ for r in rules.values()]), use_container_width=True, hide_index=True)
