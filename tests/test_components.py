"""Unit tests for core.components / core.theme -- the UI's HTML and CSS.

The security-relevant ones: everything derived from an uploaded file
(sheet names, column headers, exception text) is injected with
unsafe_allow_html, so it must come out escaped.
"""

from __future__ import annotations

import re
import unittest
from datetime import date

from core import components as c
from core.config import get_account
from core.insights import summarize
from core.models import DailyResult, ReconStatus
from core.theme import brand_css


def _r(day: int, diff: float, status: ReconStatus, population: str = "Phase 1 - FAST vs SAP") -> DailyResult:
    return DailyResult(date(2026, 8, day), population, "SAP", 100.0 + diff, "Cadency", 100.0, status)


def _first_tag(markup: str) -> str:
    return re.match(r"<(\w+)", c.flatten(markup)).group(1)


class TestEscaping(unittest.TestCase):
    def test_uploaded_text_is_escaped(self):
        hostile = '<img src=x onerror="alert(1)">'
        for markup in (
            c.loaded(1, 1, hostile),
            c.callout(f"Could not read: {hostile}", tone="alert"),
            c.chips([(hostile, hostile)]),
            c.facts([(hostile, hostile)]),
            c.export_panel([hostile], hostile),
        ):
            self.assertNotIn("<img", markup)
            self.assertIn("&lt;img", markup)

    def test_dollar_signs_are_encoded(self):
        # Streamlit's markdown renders "$...$" as LaTeX math.
        self.assertNotIn("$", c.esc("$1.00 to $2.00"))
        self.assertIn("&#36;", c.esc("$1.00"))


class TestFormatting(unittest.TestCase):
    def test_money(self):
        self.assertEqual(c.money(-1234.5), "-$1,234.50")
        self.assertEqual(c.money(0), "$0.00")

    def test_date_range(self):
        self.assertEqual(c.date_range(date(2026, 8, 3), date(2026, 8, 31)), "Aug 3 - Aug 31, 2026")
        self.assertEqual(c.date_range(date(2026, 9, 1), date(2026, 9, 1)), "Sep 1, 2026")
        self.assertEqual(c.date_range(None, None), "")

    def test_plural_and_agreement(self):
        self.assertEqual(c.plural(1, "day"), "day")
        self.assertEqual(c.plural(21, "flow-code day"), "flow-code days")
        self.assertEqual(c.needs_attention(1), "1 needs attention")
        self.assertEqual(c.needs_attention(2), "2 need attention")


class TestVerdict(unittest.TestCase):
    def test_all_clear(self):
        html = c.verdict(summarize([_r(3, 0, ReconStatus.RECONCILED)]), "day")
        self.assertIn("is-ok", html)
        self.assertIn("every day matches to the cent", html)
        self.assertIn("1 of 1 day reconciled", html)

    def test_failure_names_the_worst_day_and_flow_code(self):
        results = [
            _r(3, 0, ReconStatus.RECONCILED, "Phase 2 - +301"),
            _r(4, -10, ReconStatus.DOES_NOT_RECONCILE, "Phase 2 - +GDSCK_S"),
        ]
        html = c.verdict(summarize(results), "flow-code day", show_population=True)
        self.assertIn("is-bad", html)
        self.assertIn("1 of 2 flow-code days does not reconcile", html)
        self.assertIn("+GDSCK_S on Aug 4, 2026", html)

    def test_only_manual_review(self):
        html = c.verdict(summarize([_r(5, 0, ReconStatus.MANUAL_REVIEW, "Phase 2 - -495")]), "flow-code day")
        self.assertIn("Only manual-review items", html)

    def test_no_activity(self):
        self.assertIn("No qualifying activity", c.verdict(summarize([]), "day"))


class TestVisuals(unittest.TestCase):
    def test_heartbeat_has_one_square_per_day_with_glyph(self):
        html = c.heartbeat([_r(3, 0, ReconStatus.RECONCILED), _r(4, 5, ReconStatus.DOES_NOT_RECONCILE)])
        self.assertEqual(html.count('class="nyl-beat__day"'), 2)
        self.assertIn("nyl-sq is-ok", html)
        self.assertIn("nyl-sq is-bad", html)
        self.assertIn("✓", html)  # status is never color-only

    def test_status_matrix_marks_days_without_activity(self):
        rules = list(get_account("19803075").flow_code_rules)
        html = c.status_matrix([_r(3, 0, ReconStatus.RECONCILED, "Phase 2 - +301")], rules)
        legend = c.legend()  # the legend carries one sample square of each status
        self.assertEqual(html.count("nyl-sq is-ok") - legend.count("nyl-sq is-ok"), 1)
        self.assertEqual(html.count("nyl-sq is-empty") - legend.count("nyl-sq is-empty"), len(rules) - 1)
        self.assertIn("repeat(1, 28px)", html)


class TestMarkupShape(unittest.TestCase):
    def test_components_open_with_a_block_tag(self):
        # Markdown only passes a line through as raw HTML when it opens with
        # a block-level tag; anything else gets treated as text.
        s = summarize([_r(3, 0, ReconStatus.RECONCILED)])
        for markup in (
            c.hero("t", "e", "l", ["m"]), c.chips([("k", "v")]), c.step("01", "t"), c.source_header("A", "t"),
            c.loaded(1, 1, None), c.callout("x"), c.verdict(s, "day"), c.kpis([c.Kpi("l", "v")]),
            c.footer(), c.profile_card(), c.credit_banner(), c.how_it_works(), c.roadmap([(None, "t", "d")]),
        ):
            self.assertEqual(_first_tag(markup), "div")

    def test_flatten_leaves_no_newlines_or_indentation(self):
        flat = c.flatten(c.hero("t", "e", "l"))
        self.assertNotIn("\n", flat)
        self.assertFalse(flat.startswith(" "))

    def test_stylesheet_is_safe_to_inject(self):
        css = brand_css()
        self.assertNotIn("<", css)  # would end the <style> block early
        self.assertIn("prefers-reduced-motion", css)
        self.assertEqual(css.count("{"), css.count("}"))

    def test_sidebar_font_override_spares_nav_icons(self):
        # Forcing the body font onto the icon-font spans printed "dashboard",
        # "fact_check"... over the sidebar page titles (2026-10-27).
        css = brand_css()
        self.assertNotIn('[data-testid="stSidebarNav"] * { color: var(--nyl-white) !important; font-family', css)
        self.assertIn('[data-testid="stSidebarNav"] *:not([data-testid="stIconMaterial"]) { font-family', css)


if __name__ == "__main__":
    unittest.main()
