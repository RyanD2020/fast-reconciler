"""Phase 2 -- each bank Flow Code against its own Cadency population."""

import pandas as pd
import streamlit as st

from core import components as c
from core.insights import phase2_run_facts, summarize
from core.matching import run_phase2
from core.ui import (
    current_account,
    render,
    render_results_table,
    run_with_persistence,
    source_input,
    workbook_download,
)

account = current_account()
rules = [r for r in account.flow_code_rules if r.phase == 2]

render(
    c.hero(
        title="Treasury / bank flow codes",
        eyebrow="Phase 2 · Cash control",
        lede="Every bank flow code reconciles on its own, every day - one failure never hides behind another's match.",
        meta=[account.display_name, f"{len(rules)} flow codes", "Zero tolerance"],
    )
)
render(
    c.chips(
        [
            ("-466 outgoing EFT", "Matched on Effective Date"),
            ("GDS checks", "Split by Reference 7: C / S / I"),
            ("-495 / +195 wires", "Always manual review"),
            ("Phase 2 sign", "As exported - not yet confirmed"),
        ],
        trusted_hint_html="Flow-code rules live in <code>core/config.py</code>.",
    )
)
with st.expander("All flow-code rules for this account"):
    st.dataframe(pd.DataFrame([r.__dict__ for r in rules]), use_container_width=True, hide_index=True)

render(c.step("01", "Load the exports", "The Cadency export and the Treasury / bank statement, as downloaded."))
left, right = st.columns(2, gap="large")
with left:
    cadency_df = source_input("Cadency export", "phase2_cadency", "A", "FAST and GDS activity - the rules route each row to its flow code.")
with right:
    bank_df = source_input("Treasury / bank statement", "phase2_bank", "B", "One row per flow-code movement.")

render(c.step("02", "Reconcile", "Each flow code, each day, judged independently."))
ready = cadency_df is not None and bank_df is not None


def _compute():
    return {"result": run_phase2(cadency_df, bank_df, account), "cadency": cadency_df, "bank": bank_df}


def _announce(run):
    s = summarize(run["result"].daily_results)
    st.toast(f"Phase 2 complete - {s.reconciled} of {s.judged} flow-code days reconciled, {s.manual_review} for manual review.")


run = run_with_persistence(
    "Run Phase 2 reconciliation", "phase2_state", ready, account.account_number, _compute, on_complete=_announce
)

if run is None:
    if not ready:
        render(c.callout("Load both exports above to enable the reconciliation.", tone="info"))
else:
    result = run["result"]
    summary = summarize(result.daily_results)
    results_df = result.as_dataframe()

    render(c.verdict(summary, noun="flow-code day", show_population=True))
    if summary.total:
        render(c.kpis(c.phase2_kpis(summary, result, len(rules))))
        render(c.status_matrix(result.daily_results, rules))

        tab_results, tab_bank, tab_cadency, tab_run = st.tabs(["Daily results", "Bank detail", "Cadency detail", "Run details"])
        with tab_results:
            render_results_table(results_df)
        with tab_bank:
            st.dataframe(result.bank_detail, use_container_width=True, hide_index=True)
        with tab_cadency:
            st.dataframe(result.cadency_detail, use_container_width=True, hide_index=True)
        with tab_run:
            render(c.facts(phase2_run_facts(run["cadency"], run["bank"], account, result)))

        sheets = [
            ("Phase 2 Results", results_df),
            ("Cadency - Phase 2 Qualifying", result.cadency_detail),
            ("Bank - Phase 2 Qualifying", result.bank_detail),
            ("Cadency - Raw", run["cadency"]),
            ("Bank - Raw", run["bank"]),
        ]
        filename = f"phase2_reconciliation_{account.account_number}_{summary.first_date}_{summary.last_date}.xlsx"

        render(c.step("03", "Export", "The whole run in one workbook - results first, then the evidence behind them."))
        render(c.export_panel([name for name, _ in sheets], filename))
        workbook_download(run, sheets, filename, key="phase2")
