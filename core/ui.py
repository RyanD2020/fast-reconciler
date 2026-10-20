"""
Streamlit glue: renders core/components.py's HTML, and wraps the few
stateful widgets (file inputs, the Run button, the account selector).

Kept thin on purpose -- anything that can be a pure function lives in
components.py / insights.py / theme.py, where it's unit-tested.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import streamlit as st

from . import components
from .brand import STATUS_COLORS
from .config import ACCOUNTS, AccountConfig, get_account
from .export import export_workbook
from .io_utils import list_sheet_names, load_tabular
from .theme import brand_css

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

ACCOUNT_KEY = "account_number"


def render(markup: str) -> None:
    st.markdown(components.flatten(markup), unsafe_allow_html=True)


def apply_brand_theme() -> None:
    render(f"<style>{brand_css()}</style>")


def account_selector() -> AccountConfig:
    """The one shared account selector (sidebar). Pages read the choice via
    current_account() rather than each rendering their own."""
    st.selectbox(
        "Clearing account",
        options=list(ACCOUNTS),
        format_func=lambda acct: ACCOUNTS[acct].display_name,
        key=ACCOUNT_KEY,
    )
    return current_account()


def current_account() -> AccountConfig:
    return get_account(st.session_state.get(ACCOUNT_KEY, next(iter(ACCOUNTS))))


class _NamedBytes(io.BytesIO):
    """In-memory file with a .name, the shape load_tabular expects."""

    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


# Streamlit reruns the whole script on every interaction, and parsing a real
# Cadency export takes ~13s -- so parsing is cached on the file's bytes.
# Without this, every click re-read every file (measured 2026-10-20).
@st.cache_data(show_spinner=False, max_entries=16, ttl=3600)
def _sheet_names(data: bytes, filename: str) -> list[str] | None:
    return list_sheet_names(uploaded_file=_NamedBytes(data, filename))


@st.cache_data(show_spinner="Reading the file...", max_entries=4, ttl=3600)
def _load(data: bytes, filename: str, sheet_name: "int | str") -> pd.DataFrame:
    return load_tabular(uploaded_file=_NamedBytes(data, filename), sheet_name=sheet_name)


def _pick_sheet(label: str, key: str, sheet_names: list[str] | None) -> "int | str":
    """If the file has more than one sheet, asks which one is {label} --
    real workbooks (e.g. someone's own review file) don't always put the
    data on the first sheet. Returns the sheet name, or 0 for .csv files."""
    if not sheet_names:
        return 0
    if len(sheet_names) == 1:
        return sheet_names[0]
    return st.selectbox(f"Which sheet is the {label}?", sheet_names, key=f"{key}_sheet")


def source_input(label: str, key: str, badge: str, hint: str = "") -> pd.DataFrame | None:
    """Upload widget or Databricks Volume path for one data source. Returns
    the loaded DataFrame, or None until something loads successfully."""
    render(components.source_header(badge, label, hint))
    mode = st.radio(
        f"How will you provide the {label}?",
        ["Upload file", "Databricks Volume path"],
        key=f"{key}_mode",
        horizontal=True,
        label_visibility="collapsed",
    )
    try:
        if mode == "Upload file":
            uploaded = st.file_uploader(
                f"Upload the {label} (.csv or .xlsx)", key=f"{key}_upload", label_visibility="collapsed"
            )
            if uploaded is None:
                return None
            data, filename = uploaded.getvalue(), uploaded.name
        else:
            path = st.text_input(
                f"Volume path for the {label}",
                key=f"{key}_path",
                placeholder="/Volumes/catalog/schema/volume/file.xlsx",
                label_visibility="collapsed",
            )
            if not path:
                return None
            data, filename = Path(path).read_bytes(), Path(path).name
        sheet = _pick_sheet(label, key, _sheet_names(data, filename))
        df = _load(data, filename, sheet)
    except Exception as e:
        render(components.callout(f"Could not read the {label}: {e}", tone="alert"))
        return None

    render(components.loaded(len(df), len(df.columns), sheet if isinstance(sheet, str) else None))
    with st.expander("Preview first 20 rows"):
        st.dataframe(df.head(20), use_container_width=True, hide_index=True)
    return df


def persisted(state_key: str, account_number: str) -> Any | None:
    state = st.session_state.get(state_key)
    if state is not None and state["account_number"] == account_number:
        return state["value"]
    return None


def run_with_persistence(
    label: str,
    state_key: str,
    ready: bool,
    account_number: str,
    compute: Callable[[], Any],
    on_complete: Callable[[Any], None] | None = None,
) -> Any | None:
    """Runs compute() when the button is clicked and keeps the result in
    st.session_state, so it survives Streamlit reruns -- a dropped/reconnected
    websocket after the app idles, or simply clicking the Download button.
    st.button() is only True for the one run the click happened in, so
    without this the results would vanish on the very next rerun.

    Returns the persisted value for the selected account, or None if nothing
    has run yet (or the account changed, which deliberately drops the old
    result rather than show one account's numbers under another's name).
    """
    if st.button(label, type="primary", disabled=not ready):
        try:
            value = compute()
        except Exception as e:
            st.session_state.pop(state_key, None)
            render(components.callout(f"{label} could not run: {e}", tone="alert"))
        else:
            st.session_state[state_key] = {"value": value, "account_number": account_number}
            if on_complete is not None:
                on_complete(value)
    return persisted(state_key, account_number)


def workbook_download(run: dict, sheets: list[tuple[str, pd.DataFrame]], filename: str, key: str) -> None:
    """Builds the export workbook on request, once per run, then offers it.

    Building is expensive -- 73s for a real month of Cadency activity
    (measured 2026-10-20) -- and the pages used to rebuild it on every
    rerun, which made every click stall for over a minute. Now it's built
    only when asked for, and cached on the persisted run (a plain dict held
    in session_state, so mutating it persists across reruns).
    """
    if "workbook" not in run and st.button("Prepare Excel workbook", key=f"{key}_build"):
        with st.spinner("Building the workbook - a full month of activity can take a minute or two..."):
            run["workbook"] = export_workbook(sheets)
    if "workbook" in run:
        st.download_button(
            "Download Excel workbook", data=run["workbook"], file_name=filename, mime=XLSX_MIME, key=f"{key}_download"
        )


def render_results_table(results_df: pd.DataFrame) -> None:
    """The daily results as a table: numbers comma-formatted, Status in bold
    brand color (white/grey are the only allowed backgrounds, so status is
    colored text, not a row fill). The table view is the accessible twin of
    the heartbeat / matrix visuals -- every value is readable here."""
    status_col = list(results_df.columns).index("Status")

    def _style_status(row):
        styles = [""] * len(row)
        color = STATUS_COLORS.get(row["Status"])
        if color:
            styles[status_col] = f"color: {color}; font-weight: 700;"
        return styles

    numeric_cols = results_df.select_dtypes(include="number").columns
    styled = results_df.style.apply(_style_status, axis=1).format({col: "{:,.2f}" for col in numeric_cols})
    st.dataframe(styled, use_container_width=True, hide_index=True)
