"""
Shared Streamlit rendering helpers, reused across app.py and pages/.

Kept separate from core/io_utils.py so that module can stay Streamlit-free
and unit-testable without a running app.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .brand import BLUE, BODY_FONT, DARK_BLUE, GREY, HEADLINE_FONT, STATUS_COLORS, WHITE
from .io_utils import list_sheet_names, load_tabular
from .models import ReconStatus


def _html(markup: str) -> str:
    """Collapses a multi-line/indented HTML string to one line before handing
    it to st.markdown(unsafe_allow_html=True).

    Without this, Markdown treats any line indented 4+ spaces as a
    preformatted code block -- and Python f-strings written with normal
    nested indentation always have that much leading whitespace. The
    practical effect: the HTML never gets parsed as HTML at all, and prints
    as literal visible tag text instead (confirmed in production -- see
    git history around 2026-10-20 for the screenshot that caught this).
    """
    return " ".join(line.strip() for line in markup.strip().splitlines())


def apply_brand_theme() -> None:
    """Injects NYL brand CSS: Dark Blue / Blue / Green / white+grey only,
    Georgia headlines + Arial body, no rounded corners, no shadows, no
    gradients. Call once near the top of each page.

    Streamlit's own theming (.streamlit/config.toml) sets the base colors;
    this covers what that can't -- per-element font-family and stripping
    rounded corners/shadows -- via direct CSS targeting Streamlit's internal
    data-testid attributes. Those attribute names aren't a public API and
    can change between Streamlit versions; if the theme stops applying
    after an upgrade, this is the first place to check.
    """
    st.markdown(
        _html(
            f"""
            <style>
            html, body, [class*="css"] {{ font-family: {BODY_FONT}; }}
            h1, h2, h3, [data-testid="stMetricValue"] {{
                font-family: {HEADLINE_FONT} !important;
                color: {DARK_BLUE};
            }}
            [data-testid="stSidebar"] {{ background-color: {DARK_BLUE}; }}
            [data-testid="stSidebar"] label,
            [data-testid="stSidebar"] .stMarkdown,
            [data-testid="stSidebar"] .stMarkdown p,
            [data-testid="stSidebar"] summary,
            [data-testid="stSidebar"] h1,
            [data-testid="stSidebar"] h2,
            [data-testid="stSidebar"] h3 {{ color: {WHITE} !important; }}
            .stButton > button, .stDownloadButton > button {{
                border-radius: 0 !important;
                box-shadow: none !important;
            }}
            .stButton > button[kind="primary"] {{
                background-color: {DARK_BLUE};
                border: none;
            }}
            .stDownloadButton > button {{
                background-color: {WHITE};
                color: {BLUE};
                border: 2px solid {BLUE} !important;
            }}
            [data-testid="stExpander"] summary {{ color: {BLUE}; }}
            </style>
            """
        ),
        unsafe_allow_html=True,
    )


def _logo_mark_html(size_px: int, font_px: float) -> str:
    """CSS recreation of the NYL logo mark (blue square, stacked white
    "NEW YORK LIFE" text) based on a reference image, not an official logo
    asset file -- see core/brand.py's docstring.
    """
    return f"""
    <div style="width:{size_px}px; height:{size_px}px; background-color:{BLUE};
                display:flex; flex-direction:column; align-items:center; justify-content:center;
                flex-shrink:0; font-family:{BODY_FONT}; font-weight:700; color:{WHITE};
                text-transform:uppercase; line-height:1.05; text-align:center; font-size:{font_px}px;">
      <span>New</span><span>York</span><span>Life</span>
    </div>
    """


def render_brand_header(title: str) -> None:
    """Sticky-feeling header bar: logo mark + title, Dark Blue background."""
    st.markdown(
        _html(
            f"""
            <div style="background-color:{DARK_BLUE}; margin:-1rem -1rem 1rem -1rem;
                        padding:14px 24px; display:flex; align-items:center; gap:12px;">
              {_logo_mark_html(40, 7)}
              <span style="color:{WHITE}; font-family:{HEADLINE_FONT}; font-size:21px; font-weight:700;">
                {title}
              </span>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def render_brand_footer() -> None:
    """Footer bar: logo mark, company name, internal-use notice, contact
    line -- per the NYL brand spec.
    """
    st.markdown(
        _html(
            f"""
            <div style="background-color:{GREY}; border-top:3px solid {DARK_BLUE};
                        margin:40px -1rem -1rem -1rem; padding:16px 24px;
                        display:flex; align-items:center; gap:12px;">
              {_logo_mark_html(32, 5.5)}
              <span style="font-family:{BODY_FONT}; font-size:12px; color:{DARK_BLUE};">
                New York Life Insurance Company &mdash; For internal use only.
                Questions? Contact Ryan Doswell.
              </span>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )


def _pick_sheet(label: str, key: str, **source_kwargs) -> "int | str":
    """If the given file has more than one sheet, shows a selectbox so the
    user picks which one is {label} -- real-world workbooks (e.g. someone's
    own manual review file) aren't guaranteed to put the needed data on the
    first sheet. Returns the sheet name, or 0 for single-sheet/.csv files.
    """
    sheet_names = list_sheet_names(**source_kwargs)
    if not sheet_names:
        return 0
    if len(sheet_names) == 1:
        return sheet_names[0]
    return st.selectbox(f"Which sheet is {label}?", sheet_names, key=f"{key}_sheet")


def source_input(label: str, key: str) -> pd.DataFrame | None:
    """Renders both an upload widget and a Volume-path text input for one
    data source (both supported from day one), and returns a DataFrame, or
    None if nothing has been supplied yet.
    """
    st.subheader(label)
    mode = st.radio(
        f"How will you provide {label}?",
        ["Upload file", "Databricks Volume path"],
        key=f"{key}_mode",
        horizontal=True,
    )
    df = None
    if mode == "Upload file":
        uploaded = st.file_uploader(f"Upload {label} (.csv or .xlsx)", key=f"{key}_upload")
        if uploaded is not None:
            try:
                sheet = _pick_sheet(label, key, uploaded_file=uploaded)
                df = load_tabular(uploaded_file=uploaded, sheet_name=sheet)
            except Exception as e:
                st.error(f"Could not read {label}: {e}")
    else:
        path = st.text_input(
            f"Volume path for {label}",
            key=f"{key}_path",
            placeholder="/Volumes/catalog/schema/volume/file.xlsx",
        )
        if path:
            try:
                sheet = _pick_sheet(label, key, volume_path=path)
                df = load_tabular(volume_path=path, sheet_name=sheet)
            except Exception as e:
                st.error(f"Could not read {label}: {e}")

    if df is not None:
        st.success(f"Loaded {len(df):,} rows.")
        with st.expander(f"Preview {label}"):
            st.dataframe(df.head(20), use_container_width=True)
    return df


def run_with_persistence(label: str, state_key: str, ready: bool, account_number: str, compute):
    """Runs compute() when the button is clicked and stores the result in
    st.session_state, so it survives a Streamlit rerun -- e.g. a dropped and
    reconnected websocket after the app sits idle for a while (this is what
    was causing results to disappear and require re-clicking Run: by
    default, st.button() only returns True for the one script run the click
    happened in, so any later rerun -- a reconnect, or even clicking the
    Download button -- would otherwise wipe the results with nothing to
    show).

    Returns the persisted value for the currently selected account, or None
    if nothing has been run yet (or the account was switched since the last
    run, which deliberately invalidates the old result rather than showing
    a different account's numbers under the current selection).
    """
    if st.button(label, type="primary", disabled=not ready):
        try:
            value = compute()
        except Exception as e:
            st.error(f"{label} could not run: {e}")
            st.session_state.pop(state_key, None)
        else:
            st.session_state[state_key] = {"value": value, "account_number": account_number}

    state = st.session_state.get(state_key)
    if state is not None and state["account_number"] == account_number:
        return state["value"]
    return None


def render_results(results_df: pd.DataFrame) -> None:
    """Displays a DailyResult-derived results dataframe with the Status
    column colored per the NYL brand (white/grey are the only background
    colors allowed, so status is shown via bold colored text rather than a
    row background fill), and a one-line summary of DOES NOT RECONCILE /
    MANUAL REVIEW counts.
    """
    status_col_idx = list(results_df.columns).index("Status")

    def _style_status(row):
        styles = [""] * len(row)
        color = STATUS_COLORS.get(row["Status"])
        if color:
            styles[status_col_idx] = f"color: {color}; font-weight: 700;"
        return styles

    numeric_cols = results_df.select_dtypes(include="number").columns
    styled = results_df.style.apply(_style_status, axis=1).format({col: "{:,.2f}" for col in numeric_cols})
    st.dataframe(styled, use_container_width=True)

    n_bad = int((results_df["Status"] == ReconStatus.DOES_NOT_RECONCILE.value).sum())
    n_manual = int((results_df["Status"] == ReconStatus.MANUAL_REVIEW.value).sum())
    if n_bad:
        st.warning(f"{n_bad} row(s) do not reconcile - see the drill-down detail below.")
    if n_manual:
        st.info(f"{n_manual} row(s) flagged for manual review.")
    if not n_bad and not n_manual:
        st.success("All rows reconcile exactly.")
