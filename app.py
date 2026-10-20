"""
FAST Clearing Account Reconciler - shell / prototype.

Run locally:
    streamlit run app.py

Deployed as a Databricks App using app.yaml (see README.md for notes on
what to check/adjust before deploying).
"""

from __future__ import annotations

import streamlit as st

from core.config import ACCOUNTS, get_account
from core.export import export_workbook
from core.matching import run_phase1
from core.ui import (
    apply_brand_theme,
    render_brand_footer,
    render_brand_header,
    render_results,
    run_with_persistence,
    source_input,
)

st.set_page_config(page_title="FAST Reconciler", layout="wide")
apply_brand_theme()
render_brand_header("FAST Clearing Account Reconciler")

st.caption(
    "Shell / prototype. Phase 1 (FAST vs. SAP) and Phase 2 (Treasury) are functional - "
    "see the Phase 2 page in the sidebar. Phase 3 (Reclaims) is still stubbed."
)

# --- Account selector (the reuse layer) -------------------------------------
account_number = st.sidebar.selectbox(
    "Account",
    options=list(ACCOUNTS.keys()),
    format_func=lambda acct: ACCOUNTS[acct].display_name,
)
account = get_account(account_number)

with st.sidebar.expander("Active rules for this account"):
    # Joined into plain strings rather than passed as lists: st.write()
    # renders a list/dict via its own JSON-array widget, which ignores
    # apply_brand_theme()'s page-level CSS and was unreadable against the
    # dark sidebar (light grey box, low-contrast text).
    st.write("Reference 10 (FAST):", account.fast_reference10_value)
    st.write("Phase 1 qualifying Trans Types:", ", ".join(account.phase1_trans_type_codes))
    st.write("Phase 1 qualifying SAP Text values:", ", ".join(account.phase1_sap_text_values))
    st.caption("Edit core/config.py to change these - no other code should need to change.")

st.divider()


col1, col2 = st.columns(2)
with col1:
    cadency_df = source_input("Cadency export", "cadency")
with col2:
    sap_df = source_input("SAP export", "sap")

st.divider()

ready = cadency_df is not None and sap_df is not None

persisted = run_with_persistence(
    "Run Phase 1 Reconciliation",
    "phase1_state",
    ready,
    account.account_number,
    lambda: (run_phase1(cadency_df, sap_df, account), cadency_df, sap_df),
)

if persisted is not None:
    result, raw_cadency_df, raw_sap_df = persisted
    st.subheader("Phase 1 Results - FAST vs. SAP")
    results_df = result.as_dataframe()
    render_results(results_df)

    with st.expander("Qualifying SAP detail (drill-down)"):
        st.dataframe(result.sap_detail, use_container_width=True)
    with st.expander("Qualifying Cadency detail (drill-down)"):
        st.dataframe(result.cadency_detail, use_container_width=True)

    excel_bytes = export_workbook(
        [
            ("Phase 1 Results", results_df),
            ("Cadency - Phase 1 Qualifying", result.cadency_detail),
            ("SAP - Phase 1 Qualifying", result.sap_detail),
            ("Cadency - Raw", raw_cadency_df),
            ("SAP - Raw", raw_sap_df),
        ]
    )
    st.download_button(
        "Download Excel export",
        data=excel_bytes,
        file_name=f"phase1_reconciliation_{account.account_number}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
elif not ready:
    st.info("Load both a Cadency export and a SAP export above, then run the reconciliation.")

render_brand_footer()
