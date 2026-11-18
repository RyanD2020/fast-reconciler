"""Phase 3 -- reclaim credits (+166 / RCCR) net of DCU's Account 187 splits,
matched to the bank with timing research. Reclaim debits (-468 / RCDB /
Account 147) are still to come."""

import pandas as pd
import streamlit as st

from core import components as c
from core.insights import phase3_run_facts
from core.matching import run_phase3
from core.ui import (
    bank_statement_input,
    current_account,
    render,
    render_results_table,
    run_with_persistence,
    source_input,
    workbook_download,
)

account = current_account()
rules = {code: r for r in account.flow_code_rules if r.phase == 3 for code in r.cadency_trans_type_codes}
credit = rules.get(account.reclaim_credit_trans_type)
debit = rules.get(account.reclaim_debit_trans_type)
window = account.phase3_timing_window_days

render(
    c.hero(
        title="Reclaim netting",
        eyebrow="Phase 3 · Reclaim credits",
        lede=(
            "Cadency books every reclaim in full. When DCU splits one with another account, only part of it "
            "reaches this account's bank - Phase 3 takes DCU's split out, then matches what's left to the bank."
        ),
        meta=[account.display_name, f"{credit.flow_code if credit else '+166'} ⇄ {account.reclaim_credit_trans_type}", "Zero tolerance"],
    )
)
render(
    c.chips(
        [
            ("DCU split", "Taken off the full Cadency amount"),
            ("DCU match", "Certificate = Ref 4, contract = Ref 2"),
            ("Other accounts' DCU rows", "Ignored"),
            ("Timing", f"Bank lines up to {window} activity day either side - working assumption"),
            ("Reclaim debits -468", "Next - waiting on test data"),
        ],
        trusted_hint_html="Reclaim rules live in <code>core/config.py</code>; the timing research in <code>core/timing.py</code>.",
    )
)

render(c.step("01", "Load the files", "As received. All three can be tabs of one workbook - load it in each slot and pick the tab."))
col_a, col_b, col_c = st.columns(3, gap="large")
with col_a:
    cadency_df = source_input("Cadency export", "phase3_cadency", "A", "RCCR reclaim credits - a full export works too.")
with col_b:
    bank_df = bank_statement_input("Treasury / bank statement", "phase3_bank", "B", "+166 lines; other flow codes are ignored.")
with col_c:
    dcu_df = source_input("DCU reclaims sheet", "phase3_dcu", "C", "DCU's notice of reclaims split with another account.")

render(c.step("02", "Reconcile", "DCU splits first, then each day against the bank, then the timing research."))
ready = cadency_df is not None and bank_df is not None and dcu_df is not None


def _compute():
    return {
        "result": run_phase3(cadency_df, bank_df, dcu_df, account),
        "cadency": cadency_df,
        "bank": bank_df,
        "dcu": dcu_df,
    }


def _announce(run):
    n = len(run["result"].exceptions)
    st.toast(f"Phase 3 complete - {n} {c.plural(n, 'item')} to research.")


run = run_with_persistence(
    "Run Phase 3 reconciliation", "phase3_state", ready, account.account_number, _compute, on_complete=_announce
)

if run is None:
    if not ready:
        render(c.callout("Load all three files above to enable the reconciliation.", tone="info"))
else:
    result = run["result"]
    results_df = result.as_dataframe()
    exceptions_df = result.findings_dataframe(exceptions=True)
    timing_df = result.findings_dataframe(exceptions=False)

    render(c.phase3_verdict(result))
    if result.daily_results:
        render(c.kpis(c.phase3_kpis(result)))
        render(c.bridge(result, account.account_number))

        tabs = st.tabs(["Items to research", "Daily results", "Reclaims", "Bank detail", "DCU splits", "Run details"])
        with tabs[0]:
            if exceptions_df.empty:
                render(c.callout("Nothing to research - every reclaim ties to the bank.", tone="ok"))
            else:
                st.dataframe(exceptions_df, use_container_width=True, hide_index=True)
            with st.expander(f"Timing ties ({len(timing_df)}) - days that tie once a neighbouring day's bank lines count"):
                st.dataframe(timing_df, use_container_width=True, hide_index=True)
        with tabs[1]:
            render(
                c.callout(
                    "Judged day by day with zero tolerance, like Phases 1 and 2. The note says why a day doesn't tie.",
                    tone="info",
                )
            )
            render_results_table(results_df)
        with tabs[2]:
            st.dataframe(result.cadency_detail, use_container_width=True, hide_index=True)
        with tabs[3]:
            st.dataframe(result.bank_detail, use_container_width=True, hide_index=True)
        with tabs[4]:
            st.dataframe(result.dcu_detail, use_container_width=True, hide_index=True)
        with tabs[5]:
            render(c.facts(phase3_run_facts(run["cadency"], run["bank"], run["dcu"], account, result)))

        dates = sorted(r.recon_date for r in result.daily_results)
        sheets = [
            ("Phase 3 Results", results_df),
            ("Items to Research", exceptions_df),
            ("Timing Ties", timing_df),
            ("Cadency - Phase 3 Qualifying", result.cadency_detail),
            ("Bank - Phase 3 Qualifying", result.bank_detail),
            ("DCU Splits", result.dcu_detail),
            ("Cadency - Raw", run["cadency"]),
            ("Bank - Raw", run["bank"]),
            ("DCU - Raw", run["dcu"]),
        ]
        filename = f"phase3_reclaims_{account.account_number}_{dates[0]}_{dates[-1]}.xlsx"

        render(c.step("03", "Export", "The whole run in one workbook - results and research first, then the evidence."))
        render(c.export_panel([name for name, _ in sheets], filename))
        workbook_download(run, sheets, filename, key="phase3")

render(c.step("04", "Still to come", "Reclaim debits run against legacy Account 147."))
left, right = st.columns(2, gap="large")
with left:
    render(
        c.legacy_card(
            f"Legacy Account {account.legacy_account_147 or '-'}",
            debit.flow_code if debit else "-468",
            account.reclaim_debit_trans_type,
            "Reclaim debits",
            "Account 147 already has its own mature reconciliation - Phase 3 will consume the RCDB slice of it, "
            "not rebuild it. Waiting on test data.",
        )
    )
with right:
    render(
        c.roadmap(
            [
                ("RECONCILED", "Phase 3 · Reclaim credits", "Built. DCU splits applied; timing research on the September 2026 test data."),
                (None, "Phase 3 · Reclaim debits", "Waiting on test data for -468 / RCDB / Account 147."),
                (None, "Monthly final roundup", "Planned. A separate, secondary control - methodology still to be agreed."),
            ]
        )
    )

with st.expander("Phase 3 flow-code rules in config"):
    st.dataframe(pd.DataFrame([r.__dict__ for r in rules.values()]), use_container_width=True, hide_index=True)
