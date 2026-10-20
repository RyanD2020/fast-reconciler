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

import pandas as pd

from core.schema import (
    resolve_bank_columns,
    resolve_cadency_amount_column,
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


if __name__ == "__main__":
    unittest.main()
