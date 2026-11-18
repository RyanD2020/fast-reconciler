"""
Unit tests for core.matching.run_phase3 -- reclaim credits net of DCU splits.

Every amount and identifier here is synthetic. The scenario mirrors what
Sean's September 2026 test data showed (2026-11-18): a DCU split on one
reclaim, a DCU row for another account to ignore, bank lines landing the
next day, a Friday/Monday pair, one reclaim that never reached the bank and
one bank line with no reclaim behind it.
"""

from __future__ import annotations

import unittest
from datetime import date, datetime

import pandas as pd

from core.config import get_account
from core.matching import run_phase3
from core.models import (
    FINDING_DCU_NOT_APPLIED,
    FINDING_NO_BANK_RECEIPT,
    FINDING_NOT_IN_CADENCY,
    FINDING_TIMING,
    ReconStatus,
)

ACCT_HEADER = "Acct# 19803075 or 19803095 or 147"
AMOUNT_HEADER = "Total Amount (absolute value only)"


def cadency(rows) -> pd.DataFrame:
    """rows: (day, amount, Reference 2, Reference 4[, Reference 9[, Reference 10]])"""
    return pd.DataFrame(
        [
            {
                "DR/CR": "CR",
                "Amount": abs(r[1]),
                "True Amount": r[1],
                "Post Date": datetime(2026, 9, r[0]),
                "Reference 10": r[5] if len(r) > 5 else "FAST",
                "Reference 2": r[2],
                "Reference 4": float(r[3]),  # Excel hands these back as floats
                "Reference 9": r[4] if len(r) > 4 else "RCCR",
            }
            for r in rows
        ]
    )


def bank(rows) -> pd.DataFrame:
    """rows: (day, amount[, flow code])"""
    return pd.DataFrame(
        [{"Date": datetime(2026, 9, r[0]), "Amount": r[1], "Flow Code": r[2] if len(r) > 2 else "+166"} for r in rows]
    )


def dcu(rows) -> pd.DataFrame:
    """rows: (contract, certificate, effective day, account, amount)"""
    return pd.DataFrame(
        [
            {
                "Contract Number": r[0],
                "Certificate Number": r[1],
                "Effective Date": datetime(2026, 9, r[2]),
                ACCT_HEADER: r[3],
                AMOUNT_HEADER: r[4],
            }
            for r in rows
        ]
    )


NO_DCU = pd.DataFrame(columns=["Contract Number", "Certificate Number", "Effective Date", ACCT_HEADER, AMOUNT_HEADER])


class TestPhase3Scenario(unittest.TestCase):
    """A whole synthetic month, checked end to end."""

    @classmethod
    def setUpClass(cls):
        cad = cadency(
            [
                (1, 1200.00, "GA90011", 900000101),  # DCU splits 300.00 of this off
                (1, 450.25, "GA90012", 900000102),
                (1, 75.10, "GA90013", 900000103),  # reaches the bank on 9/2
                (2, 2000.00, "GA90021", 900000201),
                (2, 310.40, "GA90022", 900000202),
                (3, 640.00, "GA90031", 900000301),
                (3, 129.99, "GA90032", 900000302),
                (3, 88.88, "GA90033", 900000303),  # never reaches the bank
                (4, 1000.00, "GA90041", 900000401),
                (4, 333.33, "GA90042", 900000402),
                (8, 700.00, "GA90081", 900000801),  # 9/8 + 9/9 only tie together
                (8, 45.00, "GA90082", 900000802),
                (9, 2500.00, "GA90091", 900000901),
                (9, 99.99, "GA90092", 900000902),
                (1, 5000.00, "GA90000", 900000001, "CHKD"),  # not a reclaim
                (1, 777.00, "GA90000", 900000002, "RCCR", "GDS"),  # not FAST
            ]
        )
        bnk = bank(
            [
                (1, 1350.25), (2, 75.10), (2, 2310.40), (3, 769.99), (4, 1333.33),
                (8, 1200.00), (9, 2144.99), (10, 250.00),  # 250.00: no reclaim behind it
                (1, 5000.00, "+301"),  # another flow code
            ]
        )
        splits = dcu(
            [
                (90011, 900000101, 1, 19803075, 300.00),
                (90099, 900000999, 2, 19803095, 120.00),  # another account - ignored
            ]
        )
        cls.result = run_phase3(cad, bnk, splits, get_account("19803075"))

    def test_month_arithmetic(self):
        r = self.result
        self.assertEqual(r.cadency_full_total, 9572.94)
        self.assertEqual(r.dcu_split_total, 300.00)
        self.assertEqual(r.expected_total, 9272.94)
        self.assertEqual(r.bank_total, 9434.06)
        self.assertEqual(r.difference, 161.12)
        self.assertEqual(r.explained, 161.12)  # +250.00 unclaimed line, -88.88 missing reclaim
        self.assertEqual(r.unexplained, 0.0)

    def test_only_fast_rccr_and_plus_166_qualify(self):
        self.assertEqual(len(self.result.cadency_detail), 14)
        self.assertEqual(len(self.result.bank_detail), 8)

    def test_daily_status_stays_zero_tolerance(self):
        status = {r.recon_date.day: r.status for r in self.result.daily_results}
        self.assertEqual(status[4], ReconStatus.RECONCILED)
        for day in (1, 2, 3, 8, 9, 10):
            self.assertEqual(status[day], ReconStatus.DOES_NOT_RECONCILE, day)

    def test_findings(self):
        kinds = [(f.kind, f.first_date.day, f.last_date.day, f.amount) for f in self.result.findings]
        self.assertEqual(
            kinds,
            [
                (FINDING_TIMING, 1, 1, 0.0),
                (FINDING_NO_BANK_RECEIPT, 3, 3, -88.88),
                (FINDING_TIMING, 8, 9, 0.0),
                (FINDING_NOT_IN_CADENCY, 10, 10, 250.00),
            ],
        )
        missing = self.result.findings[1]
        self.assertIn("certificate 900000303", missing.detail)
        self.assertIn("contract GA90033", missing.detail)
        self.assertEqual(len(self.result.exceptions), 2)

    def test_day_counts(self):
        r = self.result
        self.assertEqual((r.days_same_day, r.days_timing, r.days_with_exceptions), (2, 3, 1))

    def test_notes_explain_each_side_of_a_timing_tie(self):
        notes = {r.recon_date.day: r.note for r in self.result.daily_results}
        self.assertIn("Timing: this day's reclaims tie exactly to bank lines on 09/01/2026 ($1,350.25) and 09/02/2026 ($75.10)", notes[1])
        self.assertIn("$75.10 of this day's bank activity belongs to reclaims posted 09/01/2026", notes[2])
        self.assertIn("once the $88.88 reclaim", notes[3])
        self.assertIn("reclaims posted 09/08/2026 - 09/09/2026 together", notes[8])
        self.assertIn("$250.00 of this day's bank activity matches no Cadency reclaim", notes[10])
        self.assertEqual(notes[4], "")  # reconciled days carry no note

    def test_detail_columns(self):
        reclaims = self.result.cadency_detail.set_index("Reference 2")
        self.assertEqual(reclaims.at["GA90011", "DCU Split"], 300.00)
        self.assertEqual(reclaims.at["GA90011", "Expected in 19803075"], 900.00)
        self.assertEqual(reclaims.at["GA90033", "Bank Tie"], "No bank receipt")
        self.assertEqual(reclaims.at["GA90041", "Bank Tie"], "Same day")
        self.assertEqual(reclaims.at["GA90013", "Bank Tie"], "Timing - bank 09/01, 09/02")
        ties_to = list(self.result.bank_detail["Ties To"])
        self.assertIn("No Cadency reclaim", ties_to)
        self.assertIn("Cadency 09/08/2026 - 09/09/2026", ties_to)

    def test_dcu_rows(self):
        statuses = list(self.result.dcu_detail["Status"])
        self.assertEqual(statuses, ["Applied", "Ignored - account 19803095"])
        self.assertEqual(self.result.dcu_status_counts(), {"applied": 1, "ignored": 1, "not_applied": 0})


class TestDcuSplits(unittest.TestCase):
    def setUp(self):
        self.account = get_account("19803075")

    def run3(self, cad_rows, bank_rows, dcu_rows):
        return run_phase3(cadency(cad_rows), bank(bank_rows), dcu(dcu_rows) if dcu_rows else NO_DCU, self.account)

    def test_dcu_split_comes_off_the_full_reclaim(self):
        # The shape of Sean's 2026-11-18 example: Cadency books the reclaim in
        # full; DCU splits part of it to another account; only the rest
        # reaches this account's bank.
        r = self.run3([(1, 1000.00, "GA91234", 900001234)], [(1, 750.00)], [(91234, 900001234, 1, 19803075, 250.00)])
        self.assertEqual(r.cadency_detail["Expected in 19803075"].iloc[0], 750.00)
        self.assertEqual(r.daily_results[0].status, ReconStatus.RECONCILED)
        self.assertEqual(r.exceptions, [])

    def test_other_account_rows_are_ignored(self):
        r = self.run3([(1, 500.00, "GA07705", 900000001)], [(1, 500.00)], [(7705, 900000001, 1, 19803095, 120.00)])
        self.assertEqual(r.dcu_split_total, 0.0)
        self.assertEqual(r.daily_results[0].status, ReconStatus.RECONCILED)
        self.assertEqual(r.dcu_detail["Status"].iloc[0], "Ignored - account 19803095")
        self.assertEqual(r.exceptions, [])

    def test_contract_digits_match_despite_zero_padding(self):
        r = self.run3([(1, 500.00, "GA07705", 900000001)], [(1, 380.00)], [(7705, 900000001, 1, 19803075, 120.00)])
        self.assertEqual(r.dcu_detail["Status"].iloc[0], "Applied")

    def test_unmatched_certificate_is_not_applied_and_is_a_finding(self):
        r = self.run3([(1, 500.00, "GA90001", 900000001)], [(1, 500.00)], [(90001, 900000999, 1, 19803075, 50.00)])
        self.assertTrue(r.dcu_detail["Status"].iloc[0].startswith("Not applied - no Cadency reclaim"))
        self.assertEqual(r.expected_total, 500.00)
        self.assertEqual([f.kind for f in r.exceptions], [FINDING_DCU_NOT_APPLIED])
        self.assertIn("certificate 900000999", r.exceptions[0].detail)

    def test_certificate_without_matching_contract_is_not_applied(self):
        r = self.run3([(1, 500.00, "GA90001", 900000001)], [(1, 450.00)], [(90002, 900000001, 1, 19803075, 50.00)])
        self.assertIn("contract (Reference 2) doesn't", r.dcu_detail["Status"].iloc[0])
        self.assertEqual(r.dcu_split_total, 0.0)

    def test_two_matches_resolved_by_effective_date(self):
        r = self.run3(
            [(1, 500.00, "GA90001", 900000001), (2, 500.00, "GA90001", 900000001)],
            [(1, 500.00), (2, 450.00)],
            [(90001, 900000001, 2, 19803075, 50.00)],
        )
        self.assertEqual(r.dcu_detail["Status"].iloc[0], "Applied")
        self.assertEqual(r.dcu_detail["Cadency Post Date"].iloc[0], date(2026, 9, 2))
        self.assertTrue(all(d.status == ReconStatus.RECONCILED for d in r.daily_results))

    def test_two_matches_on_the_same_day_are_ambiguous(self):
        r = self.run3(
            [(1, 500.00, "GA90001", 900000001), (1, 300.00, "GA90001", 900000001)],
            [(1, 800.00)],
            [(90001, 900000001, 1, 19803075, 50.00)],
        )
        self.assertIn("2 Cadency reclaims match", r.dcu_detail["Status"].iloc[0])

    def test_split_larger_than_the_reclaim_is_not_applied(self):
        r = self.run3([(1, 100.00, "GA90001", 900000001)], [(1, 100.00)], [(90001, 900000001, 1, 19803075, 150.00)])
        self.assertIn("more than the reclaim", r.dcu_detail["Status"].iloc[0])
        self.assertEqual(r.expected_total, 100.00)


class TestPhase3Inputs(unittest.TestCase):
    def test_headerless_treasury_tab_with_numeric_flow_codes(self):
        # Sean's "Sept Reclaim bank Statements" tab exactly as pd.read_excel
        # returns it: a blank first row became the header, and "+166" on
        # every row was converted to the number 166.
        raw_bank = pd.DataFrame(
            [
                [datetime(2026, 9, 1), "JPMC1009", 19803075, 400.00, 166],
                [datetime(2026, 9, 2), "JPMC1009", 19803075, 100.00, 166],
            ],
            columns=[f"Unnamed: {i}" for i in range(5)],
        )
        cad = cadency([(1, 400.00, "GA90001", 900000001), (2, 100.00, "GA90002", 900000002)])
        r = run_phase3(cad, raw_bank, NO_DCU, get_account("19803075"))
        self.assertEqual(r.bank_total, 500.00)
        self.assertTrue(all(d.status == ReconStatus.RECONCILED for d in r.daily_results))

    def test_no_activity(self):
        r = run_phase3(cadency([(1, 5.00, "GA1", 1, "CHKD")]), bank([(1, 5.00, "+301")]), NO_DCU, get_account("19803075"))
        self.assertEqual(r.daily_results, [])
        self.assertEqual(r.findings, [])

    def test_missing_dcu_column_raises_clearly(self):
        with self.assertRaisesRegex(ValueError, "DCU account"):
            run_phase3(
                cadency([(1, 5.00, "GA1", 1)]),
                bank([(1, 5.00)]),
                pd.DataFrame(columns=["Certificate Number", AMOUNT_HEADER]),
                get_account("19803075"),
            )


if __name__ == "__main__":
    unittest.main()
