"""Phase 1 -- FAST accounting activity vs. SAP, daily, zero tolerance."""

import streamlit as st

from core import components as c
from core.insights import phase1_run_facts, summarize
from core.matching import run_phase1
from core.ui import (
    current_account,
    render,
    render_results_table,
    run_with_persistence,
    source_input,
    workbook_download,
)

account = current_account()

render(
    c.hero(
        title="FAST accounting vs. SAP",
        eyebrow="Phase 1 · Daily control",
        lede="Qualifying Cadency activity must equal qualifying SAP activity - every day, to the cent.",
        meta=[account.display_name, "Population match", "Zero tolerance"],
    )
)
render(
    c.chips(
        [
            ("Cadency source", f"Reference 10 = {account.fast_reference10_value}"),
            ("Trans types", " · ".join(account.phase1_trans_type_codes)),
            ("SAP text", " · ".join(account.phase1_sap_text_values)),
            ("Date basis", "Post Date vs. Document Date"),
        ],
        trusted_hint_html="Rules live in <code>core/config.py</code> - change them there, nothing else needs to change.",
    )
)

render(c.step("01", "Load the exports", "Raw files straight from Cadency and SAP. If a workbook has several tabs, you'll be asked which sheet to use."))
left, right = st.columns(2, gap="large")
with left:
    cadency_df = source_input("Cadency export", "cadency", "A", "FAST activity, every trans type - the rules do the filtering.")
with right:
    sap_df = source_input("SAP export", "sap", "B", "GL line-item export for the clearing account.")

render(c.step("02", "Reconcile", "Every qualifying day must net to exactly zero."))
ready = cadency_df is not None and sap_df is not None


def _compute():
    return {"result": run_phase1(cadency_df, sap_df, account), "cadency": cadency_df, "sap": sap_df}


def _announce(run):
    s = summarize(run["result"].daily_results)
    st.toast(f"Phase 1 complete - {s.reconciled} of {s.total} days reconciled.")


run = run_with_persistence(
    "Run Phase 1 reconciliation", "phase1_state", ready, account.account_number, _compute, on_complete=_announce
)

if run is None:
    if not ready:
        render(c.callout("Load both exports above to enable the reconciliation.", tone="info"))
else:
    result = run["result"]
    summary = summarize(result.daily_results)
    results_df = result.as_dataframe()

    render(c.verdict(summary, noun="day"))
    render(c.kpis(c.phase1_kpis(summary, result)))
    render(c.heartbeat(result.daily_results))

    tab_results, tab_sap, tab_cadency, tab_run = st.tabs(["Daily results", "SAP detail", "Cadency detail", "Run details"])
    with tab_results:
        render_results_table(results_df)
    with tab_sap:
        st.dataframe(result.sap_detail, use_container_width=True, hide_index=True)
    with tab_cadency:
        st.dataframe(result.cadency_detail, use_container_width=True, hide_index=True)
    with tab_run:
        render(c.facts(phase1_run_facts(run["cadency"], run["sap"], account, result)))

    sheets = [
        ("Phase 1 Results", results_df),
        ("Cadency - Phase 1 Qualifying", result.cadency_detail),
        ("SAP - Phase 1 Qualifying", result.sap_detail),
        ("Cadency - Raw", run["cadency"]),
        ("SAP - Raw", run["sap"]),
    ]
    period = f"_{summary.first_date}_{summary.last_date}" if summary.first_date else ""
    filename = f"phase1_reconciliation_{account.account_number}{period}.xlsx"

    render(c.step("03", "Export", "The whole run in one workbook - results first, then the evidence behind them."))
    render(c.export_panel([name for name, _ in sheets], filename))
    workbook_download(run, sheets, filename, key="phase1")
