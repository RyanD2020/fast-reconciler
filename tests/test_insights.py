"""Unit tests for core.insights -- the numbers behind the verdict and KPI tiles."""

from __future__ import annotations

import unittest
from datetime import date

import pandas as pd

from core.config import get_account
from core.insights import flow_code_of, phase1_run_facts, summarize
from core.matching import run_phase1
from core.models import DailyResult, ReconStatus


def _result(day: int, a: float, b: float, status: ReconStatus, population: str = "Phase 1 - FAST vs SAP") -> DailyResult:
    return DailyResult(date(2026, 8, day), population, "SAP", a, "Cadency", b, status)


class TestSummarize(unittest.TestCase):
    def test_all_reconciled(self):
        s = summarize([_result(3, 10, 10, ReconStatus.RECONCILED), _result(4, 5, 5, ReconStatus.RECONCILED)])
        self.assertTrue(s.all_clear)
        self.assertEqual((s.total, s.reconciled, s.not_reconciled), (2, 2, 0))
        self.assertEqual(s.net_difference, 0.0)
        self.assertIsNone(s.worst)
        self.assertEqual((s.first_date, s.last_date, s.distinct_days), (date(2026, 8, 3), date(2026, 8, 4), 2))

    def test_worst_is_largest_absolute_gap(self):
        s = summarize([
            _result(3, 100, 90, ReconStatus.DOES_NOT_RECONCILE),
            _result(4, 50, 80, ReconStatus.DOES_NOT_RECONCILE),
            _result(5, 1, 1, ReconStatus.RECONCILED),
        ])
        self.assertFalse(s.all_clear)
        self.assertEqual(s.worst.recon_date, date(2026, 8, 4))  # |-30| beats |+10|
        self.assertEqual(s.net_difference, -20.0)
        self.assertEqual(s.gross_difference, 40.0)

    def test_manual_review_rows_are_not_judged(self):
        # A manual-review row's difference must not count against the verdict.
        s = summarize([
            _result(3, 500, 500, ReconStatus.RECONCILED, "Phase 2 - +301"),
            _result(3, -999, 0, ReconStatus.MANUAL_REVIEW, "Phase 2 - -495"),
        ])
        self.assertTrue(s.all_clear)
        self.assertEqual((s.judged, s.manual_review), (1, 1))
        self.assertEqual(s.net_difference, 0.0)

    def test_empty(self):
        s = summarize([])
        self.assertFalse(s.all_clear)
        self.assertIsNone(s.first_date)

    def test_flow_code_of(self):
        self.assertEqual(flow_code_of(_result(3, 0, 0, ReconStatus.RECONCILED, "Phase 2 - -GDSCK_I")), "-GDSCK_I")


class TestRunFacts(unittest.TestCase):
    def test_reports_the_columns_and_sign_convention_actually_used(self):
        account = get_account("19803075")
        cadency = pd.DataFrame({
            "Reference 10": ["FAST"], "Reference 9": ["5801"], "Amount": [100.0], "TA": [-100.0],
            "Post Date": [date(2026, 8, 3)],
        })
        sap = pd.DataFrame({"Text": ["Annuity Payment"], "Document Date": [date(2026, 8, 3)], "Amount in Local Currency": [100.0]})
        facts = dict(phase1_run_facts(cadency, sap, account, run_phase1(cadency, sap, account)))
        self.assertEqual(facts["Cadency amount column"], "TA")
        self.assertIn("flipped", facts["Sign convention"])
        self.assertEqual(facts["Cadency rows"], "1 loaded, 1 qualifying")

    def test_flags_the_unsigned_fallback(self):
        account = get_account("19803075")
        cadency = pd.DataFrame({"Reference 10": ["FAST"], "Reference 9": ["5801"], "Amount": [100.0], "Post Date": [date(2026, 8, 3)]})
        sap = pd.DataFrame({"Text": ["Annuity Payment"], "Document Date": [date(2026, 8, 3)], "Amount": [-100.0]})
        facts = dict(phase1_run_facts(cadency, sap, account, run_phase1(cadency, sap, account)))
        self.assertIn("unsigned fallback", facts["Cadency amount column"])


if __name__ == "__main__":
    unittest.main()
