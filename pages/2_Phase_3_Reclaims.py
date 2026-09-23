from __future__ import annotations

import pandas as pd
import streamlit as st

from core.config import ACCOUNTS

st.title("Phase 3 - Reclaim Credit / Debit vs. Legacy Accounts")

st.info(
    "Not built yet. This page will net FAST Reclaim Credit (RCCR / +166) and "
    "Reclaim Debit (RCDB / -468) activity against the tracked legacy Account "
    "187 (Reclaim Credit) and Account 147 (Reclaim Debit) activity before "
    "judging the amount attributable to the clearing account, per the "
    "procedure doc."
)

account_number = st.selectbox(
    "Account", options=list(ACCOUNTS.keys()), format_func=lambda a: ACCOUNTS[a].display_name
)
account = ACCOUNTS[account_number]

st.subheader("Phase 3 Flow Code rules already captured in config")
rules_df = pd.DataFrame([r.__dict__ for r in account.flow_code_rules if r.phase == 3])
st.dataframe(rules_df, use_container_width=True)

st.subheader("Legacy account mapping already captured in config")
st.write("Reclaim Credit (+166) legacy account:", account.legacy_account_187 or "not configured")
st.write("Reclaim Debit (-468) legacy account:", account.legacy_account_147 or "not configured")
st.caption(
    "Per the CODA meeting notes, Account 187 activity is a conditional input, "
    "not a daily one - the trigger condition for when it's required still "
    "needs to be documented with the business."
)
