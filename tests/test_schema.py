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

from core.schema import resolve_bank_columns, resolve_sap_columns, resolve_trans_type_column


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


class TestResolveBankColumns(unittest.TestCase):
    def test_resolves_flow_code_date_amount(self):
        bank_df = pd.DataFrame(columns=["Flow Code", "Date", "Amount"])
        cols = resolve_bank_columns(bank_df)
        self.assertEqual(cols["flow_code"], "Flow Code")
        self.assertEqual(cols["date"], "Date")
        self.assertEqual(cols["amount"], "Amount")


if __name__ == "__main__":
    unittest.main()
