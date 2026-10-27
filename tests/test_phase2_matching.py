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
                "Reference 7": ["E"],
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
        # Two GDS/5801 rows on the same day: one EFT (Reference 7 = E,
        # -466), one cancelled check (Reference 7 = C, +GDSCK_C). They must
        # not be summed together under either Flow Code.
        cadency = pd.DataFrame(
            {
                "Reference 10": ["GDS", "GDS"],
                "Reference 9": ["5801", "5801"],
                "Reference 7": ["E", "C"],
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

    def test_466_requires_reference7_e_not_just_absence_of_check_codes(self):
        # Per Sean (2026-09-23): EFT is positively tagged Reference 7 = E,
        # not "anything that isn't a GDSCK check code." A blank/unknown
        # Reference 7 on a GDS/5801 row must NOT be picked up by -466.
        cadency = pd.DataFrame(
            {
                "Reference 10": ["GDS"],
                "Reference 9": ["5801"],
                "Reference 7": [""],
                "Amount": [150.0],
                "Post Date": [datetime(2026, 8, 3)],
                "Effective Date": [datetime(2026, 8, 3)],
            }
        )
        bank = pd.DataFrame({"Flow Code": ["-466"], "Date": [datetime(2026, 8, 3)], "Amount": [150.0]})
        result = run_phase2(cadency, bank, self.account)
        day = result.daily_results[0]
        # The bank side still has the $150, but nothing on the Cadency side
        # qualifies (blank Reference 7 != "E"), so it shows as a mismatch.
        self.assertEqual(day.source_b_total, 0.0)
        self.assertEqual(day.status, ReconStatus.DOES_NOT_RECONCILE)

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

    def test_gdsck_i_includes_gds_dedu_issued_checks(self):
        # 9/1 test data: Treasury -GDSCK_I -58,430.66 = GDS/5801/I
        # -36,878.42 + GDS/DEDU/I -21,552.24. 5801 alone left it short.
        cadency = pd.DataFrame(
            {
                "Reference 10": ["GDS", "GDS"],
                "Reference 9": [5801, "DEDU"],
                "Reference 7": ["I", "I"],
                "TA": [-36878.42, -21552.24],
                "Post Date": [datetime(2026, 9, 1)] * 2,
                "Effective Date": [datetime(2026, 9, 1)] * 2,
            }
        )
        bank = pd.DataFrame({"Flow Code": ["-GDSCK_I"], "Date": [datetime(2026, 9, 1)], "Amount": [-58430.66]})
        day = run_phase2(cadency, bank, self.account).daily_results[0]
        self.assertEqual(day.source_b_total, -58430.66)
        self.assertEqual(day.status, ReconStatus.RECONCILED)

    def test_166_reclaim_credit_is_judged_and_surfaces_as_exception(self):
        # +166 needs Phase 3's Account 187 netting before it can tie, but it
        # must still appear in Phase 2 rather than drop off the bank side.
        cadency = pd.DataFrame(
            {
                "Reference 10": ["FAST"],
                "Reference 9": ["RCCR"],
                "Reference 7": [""],
                "TA": [12720.50],
                "Post Date": [datetime(2026, 9, 1)],
                "Effective Date": [datetime(2026, 8, 24)],
            }
        )
        bank = pd.DataFrame({"Flow Code": ["+166"], "Date": [datetime(2026, 9, 1)], "Amount": [10440.67]})
        day = run_phase2(cadency, bank, self.account).daily_results[0]
        self.assertEqual(day.population, "Phase 2 - +166")
        self.assertEqual(day.status, ReconStatus.DOES_NOT_RECONCILE)
        self.assertEqual(day.difference, -2279.83)

    def test_headerless_treasury_export_runs(self):
        cadency = pd.DataFrame(
            {
                "Reference 10": ["FAST"],
                "Reference 9": ["CHKD"],
                "Reference 7": [""],
                "TA": [430.12],
                "Post Date": [datetime(2026, 9, 1)],
                "Effective Date": [datetime(2026, 9, 1)],
            }
        )
        bank = pd.DataFrame(
            [[datetime(2026, 9, 1), "0019803075", None, 430.12, 1]],
            columns=[datetime(2026, 9, 1), "WELL1711", "0019803075", 430.12, "+301"],
        )
        day = run_phase2(cadency, bank, self.account).daily_results[0]
        self.assertEqual(day.population, "Phase 2 - +301")
        self.assertEqual(day.source_a_total, 430.12)
        self.assertEqual(day.status, ReconStatus.RECONCILED)

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
