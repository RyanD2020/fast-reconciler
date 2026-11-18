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
        meta=[account.display_name, "Phase 1 live", "Phase 2 live", "Phase 3 credits live"],
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


def _phase3_status() -> tuple[str | None, str]:
    """Phase 3 is judged on what's left to research, not day by day -- see
    components.phase3_verdict."""
    run = persisted("phase3_state", account.account_number)
    if run is None:
        return None, "Not run this session"
    result = run["result"]
    if not result.daily_results:
        return None, "No reclaim activity"
    n = len(result.exceptions)
    if n == 0 and result.difference == 0:
        return "RECONCILED", "Every reclaim accounted for"
    return "DOES NOT RECONCILE", f"{n} {c.plural(n, 'item')} to research"


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
        "Reclaim credits net of DCU's Account 187 splits, with timing research.",
        *_phase3_status(), "views/phase3.py", "Open Phase 3",
    ),
]
for column, (num, title, desc, status, label, page, link_label), delay in zip(st.columns(3, gap="medium"), cards, (0, 0.08, 0.16)):
    with column:
        render(c.phase_card(num, title, desc, status, label, delay))
        st.page_link(page, label=f"{link_label} →")

render(c.step("02", "How it works", "Three steps, no spreadsheet gymnastics."))
render(c.how_it_works())
render(c.credit_banner())
