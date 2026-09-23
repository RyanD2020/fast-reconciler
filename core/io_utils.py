"""
Loading raw source files.

Supports both input modes decided on for the shell:
  - an uploaded file object (Streamlit's UploadedFile, from st.file_uploader)
  - a Databricks Unity Catalog Volume path (e.g.
    /Volumes/catalog/schema/volume/file.xlsx), read as a normal filesystem
    path

No automatic connection to Cadency / SAP / Treasury systems is made here --
per the CODA meeting notes, v1 stays a manual-file, user-initiated tool.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd


def _resolve_source(uploaded_file, volume_path):
    if uploaded_file is not None and volume_path:
        raise ValueError("Provide either uploaded_file or volume_path, not both.")
    if uploaded_file is None and not volume_path:
        raise ValueError("Provide one of uploaded_file or volume_path.")

    if uploaded_file is not None:
        return uploaded_file, getattr(uploaded_file, "name", "")

    path = Path(volume_path)
    if not path.exists():
        raise FileNotFoundError(f"No file found at volume path: {volume_path}")
    return path, path.name


def list_sheet_names(uploaded_file=None, volume_path: Optional[str] = None) -> "list[str] | None":
    """Return the sheet names in an Excel file, or None for a .csv (which
    has no concept of sheets). A real-world export isn't guaranteed to put
    the needed data on the first sheet -- e.g. a workbook someone built for
    their own manual review may have several tabs -- so the UI uses this to
    offer a sheet picker instead of silently always reading sheet 0.
    """
    source, filename = _resolve_source(uploaded_file, volume_path)
    lower = filename.lower()
    if lower.endswith(".csv"):
        return None
    if lower.endswith((".xlsx", ".xlsm")):
        engine = "openpyxl"
    elif lower.endswith(".xls"):
        engine = "xlrd"
    else:
        raise ValueError(f"Unsupported file type for {filename!r}. Expected .csv or .xlsx.")

    sheet_names = pd.ExcelFile(source, engine=engine).sheet_names
    if hasattr(source, "seek"):
        source.seek(0)
    return sheet_names


def load_tabular(
    uploaded_file=None,
    volume_path: Optional[str] = None,
    sheet_name: "int | str" = 0,
) -> pd.DataFrame:
    """Load a Cadency / SAP / Bank / legacy export from either source.
    Exactly one of uploaded_file / volume_path should be provided.
    Supports .csv and .xlsx/.xlsm (and legacy .xls via xlrd).
    """
    source, filename = _resolve_source(uploaded_file, volume_path)
    if hasattr(source, "seek"):
        source.seek(0)
    return _read_by_extension(source, filename, sheet_name)


def _read_by_extension(source, filename: str, sheet_name) -> pd.DataFrame:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return pd.read_csv(source)
    if lower.endswith((".xlsx", ".xlsm")):
        return pd.read_excel(source, sheet_name=sheet_name, engine="openpyxl")
    if lower.endswith(".xls"):
        return pd.read_excel(source, sheet_name=sheet_name, engine="xlrd")
    raise ValueError(f"Unsupported file type for {filename!r}. Expected .csv or .xlsx.")
