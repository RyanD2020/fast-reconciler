"""
Shared Streamlit rendering helpers, reused across app.py and pages/.

Kept separate from core/io_utils.py so that module can stay Streamlit-free
and unit-testable without a running app.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .io_utils import list_sheet_names, load_tabular
from .models import ReconStatus


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
    """Color-codes and displays a DailyResult-derived results dataframe,
    and shows a one-line summary of DOES NOT RECONCILE / MANUAL REVIEW counts.
    """

    def _highlight(row):
        color = {
            ReconStatus.RECONCILED.value: "background-color: #d4edda",
            ReconStatus.DOES_NOT_RECONCILE.value: "background-color: #f8d7da",
            ReconStatus.MANUAL_REVIEW.value: "background-color: #fff3cd",
        }.get(row["Status"], "")
        return [color] * len(row)

    numeric_cols = results_df.select_dtypes(include="number").columns
    styled = results_df.style.apply(_highlight, axis=1).format({col: "{:,.2f}" for col in numeric_cols})
    st.dataframe(styled, use_container_width=True)

    n_bad = int((results_df["Status"] == ReconStatus.DOES_NOT_RECONCILE.value).sum())
    n_manual = int((results_df["Status"] == ReconStatus.MANUAL_REVIEW.value).sum())
    if n_bad:
        st.warning(f"{n_bad} row(s) do not reconcile - see the drill-down detail below.")
    if n_manual:
        st.info(f"{n_manual} row(s) flagged for manual review.")
    if not n_bad and not n_manual:
        st.success("All rows reconcile exactly.")
