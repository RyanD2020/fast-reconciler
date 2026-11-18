"""
Unit tests for core.schema column resolution.

test_resolves_real_sap_gl_export_amount_column guards a real production
bug (2026-09-24): the SAP amount candidate list had "Local Currency
Amount" instead of the real SAP GL export's "Amount in Local Currency" --
same words, different order, so it never matched and Phase 1 silently
produced $0 for every SAP row instead of raising.
"""

from __future__ import annotations

import unittest
from datetime import datetime

import pandas as pd

from core.schema import (
    flow_code_text,
    normalize_bank_export,
    normalize_code,
    resolve_bank_columns,
    resolve_cadency_amount_column,
    resolve_dcu_columns,
    resolve_sap_columns,
    resolve_trans_type_column,
)


class TestResolveSapColumns(unittest.TestCase):
    def test_resolves_real_sap_gl_export_amount_column(self):
        # Field set is the real SAP FI GL line-item export layout, per the
        # user's actual export -- not just "Text"/"Document Date"/"Amount".
        sap_df = pd.DataFrame(
            columns=[
                "Cleared/Open Items Symbol", "Assignment", "Document Number", "Business Area",
                "Document Type", "Document Date", "Posting Key", "Amount in Local Currency",
                "Local Currency", "Amount in Loc.Crcy 2", "Text", "Offsetting Account",
            ]
        )
        cols = resolve_sap_columns(sap_df)
        self.assertEqual(cols["amount"], "Amount in Local Currency")
        self.assertEqual(cols["date"], "Document Date")
        self.assertEqual(cols["text"], "Text")

    def test_plain_amount_column_still_works(self):
        sap_df = pd.DataFrame(columns=["Text", "Document Date", "Amount"])
        cols = resolve_sap_columns(sap_df)
        self.assertEqual(cols["amount"], "Amount")

    def test_missing_amount_column_raises_with_clear_message(self):
        sap_df = pd.DataFrame(columns=["Text", "Document Date", "Some Other Field"])
        with self.assertRaises(ValueError) as ctx:
            resolve_sap_columns(sap_df)
        self.assertIn("SAP Amount", str(ctx.exception))
        self.assertIn("Some Other Field", str(ctx.exception))


class TestResolveTransTypeColumn(unittest.TestCase):
    def test_resolves_reference_9(self):
        cadency_df = pd.DataFrame(columns=["Reference 10", "Reference 9", "Amount"])
        self.assertEqual(resolve_trans_type_column(cadency_df), "Reference 9")


class TestResolveCadencyAmountColumn(unittest.TestCase):
    def test_prefers_ta_when_both_ta_and_amount_present(self):
        # Real Cadency exports have both columns simultaneously -- TA
        # (signed) and Amount (unsigned) -- this must NOT be treated as an
        # ambiguity error the way other candidate lists are.
        cadency_df = pd.DataFrame(columns=["Reference 10", "Reference 9", "TA", "Amount", "Post Date"])
        self.assertEqual(resolve_cadency_amount_column(cadency_df), "TA")

    def test_prefers_true_amount_over_amount(self):
        cadency_df = pd.DataFrame(columns=["Reference 10", "Reference 9", "True Amount", "Amount"])
        self.assertEqual(resolve_cadency_amount_column(cadency_df), "True Amount")

    def test_falls_back_to_amount_when_nothing_else_present(self):
        cadency_df = pd.DataFrame(columns=["Reference 10", "Reference 9", "Amount"])
        self.assertEqual(resolve_cadency_amount_column(cadency_df), "Amount")

    def test_raises_when_nothing_present(self):
        cadency_df = pd.DataFrame(columns=["Reference 10", "Reference 9"])
        with self.assertRaises(ValueError):
            resolve_cadency_amount_column(cadency_df)


class TestResolveBankColumns(unittest.TestCase):
    def test_resolves_flow_code_date_amount(self):
        bank_df = pd.DataFrame(columns=["Flow Code", "Date", "Amount"])
        cols = resolve_bank_columns(bank_df)
        self.assertEqual(cols["flow_code"], "Flow Code")
        self.assertEqual(cols["date"], "Date")
        self.assertEqual(cols["amount"], "Amount")


class TestNormalizeBankExport(unittest.TestCase):
    """The real Treasury export (9.1 Treasury.xlsx) has no header row --
    read with one, the first transaction becomes the column names and
    Phase 2 failed with "Could not find the Bank Flow Code column"."""

    def _as_read_with_header(self):
        # Exactly what pd.read_excel(header=0) hands back for the 9.1 file:
        # row 1 promoted to column labels, footer total row at the bottom.
        return pd.DataFrame(
            [
                [datetime(2026, 9, 1), "CL790", "0019803075", -58430.66, "-GDSCK_I", None, None],
                [datetime(2026, 9, 1), "JPMC1009", "0019803075", 9352.75, "+166", None, "not match"],
                [datetime(2026, 9, 1), "0019803075", None, -43867.55, 3, None, None],
            ],
            columns=[datetime(2026, 9, 1), "CL790", "0019803075", 5210.36, "+GDSCK_S", "Unnamed: 5", "Unnamed: 6"],
        )

    def test_headerless_export_keeps_first_row_and_drops_footer(self):
        df = normalize_bank_export(self._as_read_with_header())
        self.assertEqual(list(df["Flow Code"]), ["+GDSCK_S", "-GDSCK_I", "+166"])
        self.assertEqual(list(df["Amount"]), [5210.36, -58430.66, 9352.75])
        self.assertEqual(list(df["Account"]), ["19803075"] * 3)
        cols = resolve_bank_columns(df)
        self.assertEqual((cols["flow_code"], cols["date"], cols["amount"]), ("Flow Code", "Date", "Amount"))

    def test_headered_export_passes_through_unchanged(self):
        bank_df = pd.DataFrame({"Flow Code": ["+301"], "Date": [datetime(2026, 8, 3)], "Amount": [500.0]})
        self.assertIs(normalize_bank_export(bank_df), bank_df)

    def test_blank_first_row_and_numeric_flow_codes(self):
        # Sean's Phase 3 "Sept Reclaim bank Statements" tab (2026-11-18): row 1
        # is empty, so pandas names the columns "Unnamed: n"; every code is
        # "+166", so pandas reads the column as the number 166. Before this
        # fix the file failed with "Could not find the Bank Flow Code column".
        raw = pd.DataFrame(
            [
                [datetime(2026, 9, 1), "JPMC1009", 19803075, 1350.25, 166, None],
                [datetime(2026, 9, 3), "JPMC1009", 19803075, 75.10, 166, "note"],
                [datetime(2026, 9, 3), "0019803075", None, 1425.35, 2, None],  # footer: count, no account
            ],
            columns=[f"Unnamed: {i}" for i in range(6)],
        )
        df = normalize_bank_export(raw)
        self.assertEqual(list(df["Flow Code"]), ["+166", "+166"])
        self.assertEqual(list(df["Amount"]), [1350.25, 75.10])
        self.assertEqual(list(df["Account"]), ["19803075"] * 2)
        self.assertEqual(df["Column 6"].iloc[1], "note")

    def test_blank_first_row_without_flow_codes_is_left_alone(self):
        raw = pd.DataFrame([[1, 2, 3, 4, 5]], columns=[f"Unnamed: {i}" for i in range(5)])
        self.assertIs(normalize_bank_export(raw), raw)

    def test_unrecognised_layout_still_raises_the_normal_error(self):
        bank_df = pd.DataFrame(columns=["Something", "Else"])
        with self.assertRaises(ValueError):
            resolve_bank_columns(normalize_bank_export(bank_df))


class TestFlowCodeText(unittest.TestCase):
    def test_codes_read_as_numbers_get_their_sign_back(self):
        self.assertEqual(flow_code_text(166), "+166")
        self.assertEqual(flow_code_text(166.0), "+166")
        self.assertEqual(flow_code_text(-468), "-468")
        self.assertEqual(flow_code_text(" +GDSCK_S "), "+GDSCK_S")

    def test_non_codes(self):
        for value in (None, float("nan"), "", "Total", 1.5, True):
            self.assertIsNone(flow_code_text(value), value)


class TestResolveDcuColumns(unittest.TestCase):
    REAL_HEADER = [
        "Contract Number", "Certificate Number", "Cycle Date", "Effective Date", "Debit Account",
        "Acct# 19803075 or 19803095 or 147", "Trans Type", "Total Amount (absolute value only)", "IA Acct Notes",
    ]

    def test_resolves_the_real_dcu_sheet(self):
        cols = resolve_dcu_columns(pd.DataFrame(columns=self.REAL_HEADER))
        self.assertEqual(
            cols,
            {
                "certificate": "Certificate Number",
                "contract": "Contract Number",
                "effective_date": "Effective Date",
                "account": "Acct# 19803075 or 19803095 or 147",
                "amount": "Total Amount (absolute value only)",
            },
        )

    def test_account_column_matched_on_its_prefix(self):
        cols = resolve_dcu_columns(pd.DataFrame(columns=["Certificate Number", "Acct# 19803075 or 187", "Total Amount"]))
        self.assertEqual(cols["account"], "Acct# 19803075 or 187")
        self.assertIsNone(cols["contract"])
        self.assertIsNone(cols["effective_date"])

    def test_missing_required_column_raises(self):
        with self.assertRaisesRegex(ValueError, "Certificate"):
            resolve_dcu_columns(pd.DataFrame(columns=["Acct#", "Total Amount"]))


class TestNormalizeCode(unittest.TestCase):
    def test_int_float_and_string_codes_all_match(self):
        codes = normalize_code(pd.Series([5801, 5801.0, " 5801 ", "DEDU", None], dtype=object))
        self.assertEqual(list(codes), ["5801", "5801", "5801", "DEDU", ""])


if __name__ == "__main__":
    unittest.main()
