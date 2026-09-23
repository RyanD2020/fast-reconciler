from __future__ import annotations

import pandas as pd
import streamlit as st

from core.config import ACCOUNTS
from core.export import export_workbook
from core.matching import run_phase2
from core.ui import render_results, source_input

st.title("Phase 2 - Treasury / Bank Flow Code Matching")
st.caption(
    "Each bank Flow Code reconciles independently, daily, against its own Cadency "
    "population. -466 uses Cadency Effective Date (settlement-delay exception). "
    "-495 / +195 are always flagged MANUAL REVIEW - FAST does not yet generate "
    "WIRE / INCO transactions natively."
)

account_number = st.selectbox(
    "Account", options=list(ACCOUNTS.keys()), format_func=lambda a: ACCOUNTS[a].display_name
)
account = ACCOUNTS[account_number]

with st.expander("Active Flow Code rules for this account"):
    rules_df = pd.DataFrame(
        [r.__dict__ for r in account.flow_code_rules if r.phase == 2]
    )
    st.dataframe(rules_df, use_container_width=True)
    st.caption("Edit core/config.py to change these - no other code should need to change.")

st.divider()

col1, col2 = st.columns(2)
with col1:
    cadency_df = source_input("Cadency export", "phase2_cadency")
with col2:
    bank_df = source_input("Treasury / bank statement export", "phase2_bank")

st.divider()

ready = cadency_df is not None and bank_df is not None

if st.button("Run Phase 2 Reconciliation", type="primary", disabled=not ready):
    try:
        result = run_phase2(cadency_df, bank_df, account)
    except Exception as e:
        st.error(f"Phase 2 could not run: {e}")
    else:
        st.subheader("Phase 2 Results - Cadency vs. Bank, by Flow Code")
        results_df = result.as_dataframe()
        if results_df.empty:
            st.warning("No qualifying rows found for any Phase 2 Flow Code in the files provided.")
        else:
            render_results(results_df)

        with st.expander("Qualifying bank detail (drill-down)"):
            st.dataframe(result.bank_detail, use_container_width=True)
        with st.expander("Qualifying Cadency detail (drill-down)"):
            st.dataframe(result.cadency_detail, use_container_width=True)

        if not results_df.empty:
            excel_bytes = export_workbook(
                [
                    ("Phase 2 Results", results_df),
                    ("Cadency - Phase 2 Qualifying", result.cadency_detail),
                    ("Bank - Phase 2 Qualifying", result.bank_detail),
                    ("Cadency - Raw", cadency_df),
                    ("Bank - Raw", bank_df),
                ]
            )
            st.download_button(
                "Download Excel export",
                data=excel_bytes,
                file_name=f"phase2_reconciliation_{account.account_number}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
elif not ready:
    st.info(
        "Load both a Cadency export and a Treasury/bank statement export above, "
        "then run the reconciliation."
    )
