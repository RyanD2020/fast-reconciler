"""
Unit tests for core.matching.run_phase1.

Run with:
    python -m unittest discover -s tests
(pytest works too if it's installed; these use plain unittest so no extra
dependency is required to run them.)
"""

from __future__ import annotations

import unittest
from datetime import datetime

import pandas as pd

from core.config import get_account
from core.matching import run_phase1
from core.models import ReconStatus


class TestPhase1Matching(unittest.TestCase):
    def setUp(self):
        self.account = get_account("19803075")

    def test_matching_day_reconciles(self):
        cadency = pd.DataFrame(
            {
                "Reference 10": ["FAST", "FAST", "GDS"],
                "Reference 9": ["OVER", "5801", "5801"],  # last row excluded: Reference 10 == GDS
                "Amount": [100.0, 50.0, 999.0],
                "Post Date": [datetime(2026, 7, 1)] * 3,
            }
        )
        sap = pd.DataFrame(
            {
                "Text": ["Annuity Payment", "Write Off", "Something Else"],
                "Document Date": [datetime(2026, 7, 1)] * 3,
                "Amount": [100.0, 50.0, 12345.0],  # last row excluded: Text not qualifying
            }
        )
        result = run_phase1(cadency, sap, self.account)

        self.assertEqual(len(result.daily_results), 1)
        day = result.daily_results[0]
        self.assertEqual(day.status, ReconStatus.RECONCILED)
        self.assertEqual(day.difference, 0.0)
        self.assertEqual(day.source_a_total, 150.0)
        self.assertEqual(day.source_b_total, 150.0)

    def test_mismatched_day_does_not_reconcile(self):
        cadency = pd.DataFrame(
            {
                "Reference 10": ["FAST"],
                "Reference 9": ["OVER"],
                "Amount": [100.0],
                "Post Date": [datetime(2026, 7, 2)],
            }
        )
        sap = pd.DataFrame(
            {
                "Text": ["Annuity Payment"],
                "Document Date": [datetime(2026, 7, 2)],
                "Amount": [150.0],
            }
        )
        result = run_phase1(cadency, sap, self.account)
        day = result.daily_results[0]
        self.assertEqual(day.status, ReconStatus.DOES_NOT_RECONCILE)
        self.assertEqual(day.difference, 50.0)

    def test_non_qualifying_trans_type_excluded(self):
        cadency = pd.DataFrame(
            {
                "Reference 10": ["FAST", "FAST"],
                "Reference 9": ["OVER", "CHKD"],  # CHKD is a Phase 2 population, not Phase 1
                "Amount": [100.0, 5000.0],
                "Post Date": [datetime(2026, 7, 3)] * 2,
            }
        )
        sap = pd.DataFrame(
            {
                "Text": ["Annuity Payment"],
                "Document Date": [datetime(2026, 7, 3)],
                "Amount": [100.0],
            }
        )
        result = run_phase1(cadency, sap, self.account)
        day = result.daily_results[0]
        self.assertEqual(day.source_b_total, 100.0)  # CHKD row correctly excluded
        self.assertEqual(day.status, ReconStatus.RECONCILED)

    def test_ambiguous_trans_type_column_raises(self):
        # Both candidate columns present -> can't tell which is authoritative.
        cadency = pd.DataFrame(
            {
                "Reference 10": ["FAST"],
                "TR No": ["5801"],
                "Reference 9": ["5801"],
                "Amount": [100.0],
                "Post Date": [datetime(2026, 7, 1)],
            }
        )
        sap = pd.DataFrame(
            {
                "Text": ["Annuity Payment"],
                "Document Date": [datetime(2026, 7, 1)],
                "Amount": [100.0],
            }
        )
        with self.assertRaises(ValueError):
            run_phase1(cadency, sap, self.account)

    def test_missing_trans_type_column_raises(self):
        cadency = pd.DataFrame(
            {
                "Reference 10": ["FAST"],
                "Amount": [100.0],
                "Post Date": [datetime(2026, 7, 1)],
            }
        )
        sap = pd.DataFrame(
            {
                "Text": ["Annuity Payment"],
                "Document Date": [datetime(2026, 7, 1)],
                "Amount": [100.0],
            }
        )
        with self.assertRaises(ValueError):
            run_phase1(cadency, sap, self.account)


if __name__ == "__main__":
    unittest.main()
