"""
Unit tests for core.matching.run_phase2.

Run with:
    python -m unittest discover -s tests
"""

from __future__ import annotations

import unittest
from datetime import datetime

import pandas as pd

from core.config import get_account
from core.matching import run_phase2
from core.models import ReconStatus


class TestPhase2Matching(unittest.TestCase):
    def setUp(self):
        self.account = get_account("19803075")

    def test_matching_flow_code_reconciles(self):
        cadency = pd.DataFrame(
            {
                "Reference 10": ["FAST"],
                "Reference 9": ["CHKD"],
                "Reference 7": [""],
                "Amount": [500.0],
                "Post Date": [datetime(2026, 8, 3)],
                "Effective Date": [datetime(2026, 8, 3)],
            }
        )
        bank = pd.DataFrame({"Flow Code": ["+301"], "Date": [datetime(2026, 8, 3)], "Amount": [500.0]})
        result = run_phase2(cadency, bank, self.account)

        self.assertEqual(len(result.daily_results), 1)
        day = result.daily_results[0]
        self.assertEqual(day.population, "Phase 2 - +301")
        self.assertEqual(day.status, ReconStatus.RECONCILED)

    def test_mismatched_flow_code_does_not_reconcile(self):
        cadency = pd.DataFrame(
            {
                "Reference 10": ["FAST"],
                "Reference 9": ["CHKD"],
                "Reference 7": [""],
                "Amount": [500.0],
                "Post Date": [datetime(2026, 8, 3)],
                "Effective Date": [datetime(2026, 8, 3)],
            }
        )
        bank = pd.DataFrame({"Flow Code": ["+301"], "Date": [datetime(2026, 8, 3)], "Amount": [450.0]})
        result = run_phase2(cadency, bank, self.account)
        day = result.daily_results[0]
        self.assertEqual(day.status, ReconStatus.DOES_NOT_RECONCILE)
        self.assertEqual(day.difference, -50.0)

    def test_466_uses_effective_date_not_post_date(self):
        # Post Date 8/4, Effective Date 8/6 - bank activity settles 8/6.
        cadency = pd.DataFrame(
            {
                "Reference 10": ["GDS"],
                "Reference 9": ["5801"],
                "Reference 7": [""],
                "Amount": [150.0],
                "Post Date": [datetime(2026, 8, 4)],
                "Effective Date": [datetime(2026, 8, 6)],
            }
        )
        bank = pd.DataFrame({"Flow Code": ["-466"], "Date": [datetime(2026, 8, 6)], "Amount": [150.0]})
        result = run_phase2(cadency, bank, self.account)

        self.assertEqual(len(result.daily_results), 1)
        day = result.daily_results[0]
        self.assertEqual(day.recon_date, datetime(2026, 8, 6).date())
        self.assertEqual(day.status, ReconStatus.RECONCILED)

    def test_gdsck_reference7_splits_from_466(self):
        # Two GDS/5801 rows on the same day: one plain EFT (-466), one
        # cancelled check (Reference 7 = C, +GDSCK_C). They must not be
        # summed together under either Flow Code.
        cadency = pd.DataFrame(
            {
                "Reference 10": ["GDS", "GDS"],
                "Reference 9": ["5801", "5801"],
                "Reference 7": ["", "C"],
                "Amount": [150.0, 120.0],
                "Post Date": [datetime(2026, 8, 3)] * 2,
                "Effective Date": [datetime(2026, 8, 3)] * 2,
            }
        )
        bank = pd.DataFrame(
            {
                "Flow Code": ["-466", "+GDSCK_C"],
                "Date": [datetime(2026, 8, 3), datetime(2026, 8, 3)],
                "Amount": [150.0, 120.0],
            }
        )
        result = run_phase2(cadency, bank, self.account)
        by_flow_code = {r.population: r for r in result.daily_results}

        self.assertEqual(by_flow_code["Phase 2 - -466"].source_b_total, 150.0)
        self.assertEqual(by_flow_code["Phase 2 - +GDSCK_C"].source_b_total, 120.0)
        self.assertEqual(by_flow_code["Phase 2 - -466"].status, ReconStatus.RECONCILED)
        self.assertEqual(by_flow_code["Phase 2 - +GDSCK_C"].status, ReconStatus.RECONCILED)

    def test_495_always_manual_review_even_when_amounts_match(self):
        cadency = pd.DataFrame(
            {
                "Reference 10": ["FAST"],
                "Reference 9": ["WIRE"],
                "Reference 7": [""],
                "Amount": [-1000.0],
                "Post Date": [datetime(2026, 8, 5)],
                "Effective Date": [datetime(2026, 8, 5)],
            }
        )
        bank = pd.DataFrame({"Flow Code": ["-495"], "Date": [datetime(2026, 8, 5)], "Amount": [-1000.0]})
        result = run_phase2(cadency, bank, self.account)
        day = result.daily_results[0]
        self.assertEqual(day.status, ReconStatus.MANUAL_REVIEW)

    def test_each_flow_code_independent_one_failure_does_not_affect_others(self):
        cadency = pd.DataFrame(
            {
                "Reference 10": ["FAST", "FAST"],
                "Reference 9": ["CHKD", "BRCR"],
                "Reference 7": ["", ""],
                "Amount": [500.0, 75.0],
                "Post Date": [datetime(2026, 8, 3), datetime(2026, 8, 4)],
                "Effective Date": [datetime(2026, 8, 3), datetime(2026, 8, 4)],
            }
        )
        bank = pd.DataFrame(
            {
                "Flow Code": ["+301", "+168"],
                "Date": [datetime(2026, 8, 3), datetime(2026, 8, 4)],
                "Amount": [450.0, 75.0],  # +301 mismatched, +168 matches
            }
        )
        result = run_phase2(cadency, bank, self.account)
        by_flow_code = {r.population: r.status for r in result.daily_results}

        self.assertEqual(by_flow_code["Phase 2 - +301"], ReconStatus.DOES_NOT_RECONCILE)
        self.assertEqual(by_flow_code["Phase 2 - +168"], ReconStatus.RECONCILED)


if __name__ == "__main__":
    unittest.main()
