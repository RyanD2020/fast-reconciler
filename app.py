"""
FAST Clearing Account Reconciler -- entrypoint and router.

Run locally:
    streamlit run app.py

Deployed as a Databricks App using app.yaml (see DEPLOYMENT.md).

Everything shared across pages lives here and runs on every rerun: the brand
theme, the sidebar (account selector + credits) and the footer. The pages in
views/ render only their own content.
"""

from __future__ import annotations

import streamlit as st

from core import components
from core.brand import BUILT_BY, COMMUNITY, TEAM
from core.ui import account_selector, apply_brand_theme, render

st.set_page_config(
    page_title="FAST Reconciler | New York Life",
    page_icon="🟦",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get help": None,
        "Report a bug": None,
        "About": f"**FAST Clearing Account Reconciler**\n\nBuilt by {BUILT_BY} - {TEAM} - {COMMUNITY}",
    },
)
apply_brand_theme()

pages = st.navigation(
    {
        "Workspace": [
            st.Page("views/overview.py", title="Overview", icon=":material/dashboard:", default=True),
        ],
        "Reconciliation": [
            st.Page("views/phase1.py", title="Phase 1 · FAST vs. SAP", icon=":material/fact_check:"),
            st.Page("views/phase2.py", title="Phase 2 · Treasury", icon=":material/account_balance:"),
            st.Page("views/phase3.py", title="Phase 3 · Reclaims", icon=":material/assignment_return:"),
        ],
    }
)

with st.sidebar:
    account_selector()
    render(components.profile_card())

pages.run()

render(components.footer())
