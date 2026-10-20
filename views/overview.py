"""Overview -- the landing page: where each phase stands this session."""

import streamlit as st

from core import components as c
from core.insights import summarize
from core.ui import current_account, persisted, render

account = current_account()

render(
    c.hero(
        title="Reconciliation command center",
        eyebrow="Workspace · Overview",
        lede=(
            "Load the raw exports, let the documented rules route every row, and get an exact-match "
            "verdict for every day - with the workbook to prove it."
        ),
        meta=[account.display_name, "Phase 1 live", "Phase 2 live", "Phase 3 in design"],
    )
)


def _status(state_key: str, noun: str) -> tuple[str | None, str]:
    run = persisted(state_key, account.account_number)
    if run is None:
        return None, "Not run this session"
    s = summarize(run["result"].daily_results)
    if s.total == 0:
        return None, "No qualifying activity"
    if s.all_clear:
        return "RECONCILED", f"{s.reconciled} of {s.judged} {c.plural(s.judged, noun)} reconciled"
    return "DOES NOT RECONCILE", f"{s.not_reconciled} of {s.judged} {c.plural(s.judged, noun)} {'needs' if s.not_reconciled == 1 else 'need'} attention"


render(c.step("01", "This session", "Where each phase stands for the selected account."))
cards = [
    (
        "01", "FAST accounting vs. SAP",
        "Daily population match between qualifying Cadency and SAP activity.",
        *_status("phase1_state", "day"), "views/phase1.py", "Open Phase 1",
    ),
    (
        "02", "Treasury / bank flow codes",
        "Each bank flow code against its own Cadency population, independently.",
        *_status("phase2_state", "flow-code day"), "views/phase2.py", "Open Phase 2",
    ),
    (
        "03", "Reclaim netting",
        "RCCR / RCDB activity netted against legacy Accounts 187 and 147.",
        None, "In design", "views/phase3.py", "Open Phase 3",
    ),
]
for column, (num, title, desc, status, label, page, link_label), delay in zip(st.columns(3, gap="medium"), cards, (0, 0.08, 0.16)):
    with column:
        render(c.phase_card(num, title, desc, status, label, delay))
        st.page_link(page, label=f"{link_label} →")

render(c.step("02", "How it works", "Three steps, no spreadsheet gymnastics."))
render(c.how_it_works())
render(c.credit_banner())
