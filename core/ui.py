"""
Shared Streamlit rendering helpers, reused across app.py and pages/.

Kept separate from core/io_utils.py so that module can stay Streamlit-free
and unit-testable without a running app.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .io_utils import load_tabular
from .models import ReconStatus


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
                df = load_tabular(uploaded_file=uploaded)
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
                df = load_tabular(volume_path=path)
            except Exception as e:
                st.error(f"Could not read {label}: {e}")

    if df is not None:
        st.success(f"Loaded {len(df):,} rows.")
        with st.expander(f"Preview {label}"):
            st.dataframe(df.head(20), use_container_width=True)
    return df


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

    st.dataframe(results_df.style.apply(_highlight, axis=1), use_container_width=True)

    n_bad = int((results_df["Status"] == ReconStatus.DOES_NOT_RECONCILE.value).sum())
    n_manual = int((results_df["Status"] == ReconStatus.MANUAL_REVIEW.value).sum())
    if n_bad:
        st.warning(f"{n_bad} row(s) do not reconcile - see the drill-down detail below.")
    if n_manual:
        st.info(f"{n_manual} row(s) flagged for manual review.")
    if not n_bad and not n_manual:
        st.success("All rows reconcile exactly.")
