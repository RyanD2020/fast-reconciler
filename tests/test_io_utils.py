"""
Unit tests for core.io_utils.list_sheet_names / load_tabular.
"""

from __future__ import annotations

import io
import unittest

import pandas as pd

from core.io_utils import list_sheet_names, load_tabular


class FakeUploadedFile(io.BytesIO):
    """Stands in for Streamlit's UploadedFile: a BytesIO with a .name."""

    def __init__(self, data: bytes, name: str):
        super().__init__(data)
        self.name = name


def _make_xlsx_bytes(sheets: dict) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for name, df in sheets.items():
            df.to_excel(writer, sheet_name=name, index=False)
    return buffer.getvalue()


class TestListSheetNames(unittest.TestCase):
    def test_csv_has_no_sheets(self):
        f = FakeUploadedFile(b"a,b\n1,2\n", "data.csv")
        self.assertIsNone(list_sheet_names(uploaded_file=f))

    def test_returns_sheet_names_in_order(self):
        data = _make_xlsx_bytes(
            {"Cadency match to SAP": pd.DataFrame({"x": [1]}), "SAP Match to Cadency": pd.DataFrame({"y": [2]})}
        )
        f = FakeUploadedFile(data, "IA Accting - Phase 1 Data.xlsx")
        self.assertEqual(list_sheet_names(uploaded_file=f), ["Cadency match to SAP", "SAP Match to Cadency"])

    def test_single_sheet_workbook(self):
        data = _make_xlsx_bytes({"Sheet1": pd.DataFrame({"x": [1]})})
        f = FakeUploadedFile(data, "single.xlsx")
        self.assertEqual(list_sheet_names(uploaded_file=f), ["Sheet1"])

    def test_can_still_load_a_sheet_after_listing_them(self):
        # Guards against the file stream being left exhausted/unseeked
        # after list_sheet_names reads it once.
        data = _make_xlsx_bytes({"First": pd.DataFrame({"x": [1, 2]}), "Second": pd.DataFrame({"y": [3, 4]})})
        f = FakeUploadedFile(data, "workbook.xlsx")

        sheets = list_sheet_names(uploaded_file=f)
        df = load_tabular(uploaded_file=f, sheet_name=sheets[1])

        self.assertEqual(list(df["y"]), [3, 4])


if __name__ == "__main__":
    unittest.main()
