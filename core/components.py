"""
HTML building blocks for the UI, styled by the nyl-* classes in core/theme.py.

Pure functions returning HTML strings -- no Streamlit import -- so they're
unit-testable and can be rendered in a static preview. core/ui.py::render()
hands them to st.markdown.

Every piece of dynamic text goes through esc(): file names, sheet names,
column headers and exception messages all come from uploaded files, and
these strings are injected with unsafe_allow_html. esc() also encodes "$",
because Streamlit's markdown treats "$...$" as LaTeX math.

Each builder returns markup whose first tag is a <div> -- Markdown only
passes a line through as raw HTML when it opens with a block-level tag.
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .brand import BUILT_BY, STATUS_CSS, STATUS_GLYPHS
from .config import FlowCodeRule
from .insights import ReconSummary, flow_code_of
from .models import DailyResult, Phase1Result, Phase2Result, Phase3Result


def flatten(markup: str) -> str:
    """Collapse multi-line, indented markup onto one line before it reaches
    st.markdown. Markdown treats any line indented 4+ spaces as a code
    block, so without this the HTML prints as literal tag text instead of
    rendering (seen in production 2026-10-20)."""
    return " ".join(line.strip() for line in markup.strip().splitlines())


def esc(value: object) -> str:
    return html.escape(str(value), quote=True).replace("$", "&#36;")


def money(value: float) -> str:
    """-1234.5 -> "-$1,234.50" (plain text; pass through esc() for HTML)."""
    return f"{'-' if value < 0 else ''}${abs(value):,.2f}"


def plural(n: int, noun: str) -> str:
    return noun if n == 1 else f"{noun}s"


def needs_attention(n: int) -> str:
    return f"{n} {'needs' if n == 1 else 'need'} attention"


def short_date(d: date) -> str:
    return f"{d:%b} {d.day}, {d.year}"


def date_range(first: date | None, last: date | None) -> str:
    if first is None or last is None:
        return ""
    if first == last:
        return short_date(first)
    if first.year == last.year:
        return f"{first:%b} {first.day} - {last:%b} {last.day}, {last.year}"
    return f"{short_date(first)} - {short_date(last)}"


def _sq(status: str | None, title: str = "", delay: float | None = None) -> str:
    style = f' style="animation-delay:{delay:.3f}s"' if delay is not None else ""
    if status is None:
        return f'<span class="nyl-sq is-empty" title="{esc(title)}"{style}></span>'
    return (
        f'<span class="nyl-sq is-{STATUS_CSS[status]}" title="{esc(title)}"{style}>'
        f"{STATUS_GLYPHS[status]}</span>"
    )


def logo_mark(size: int = 48) -> str:
    """CSS recreation of the NYL logo mark from the user's reference image --
    not an official asset; see core/brand.py."""
    font = round(size * 0.2, 1)
    return (
        f'<div class="nyl-logo" style="width:{size}px;height:{size}px;font-size:{font}px" '
        f'role="img" aria-label="New York Life"><span>New</span><span>York</span><span>Life</span></div>'
    )


def hero(title: str, eyebrow: str, lede: str, meta: Iterable[str] = ()) -> str:
    # 35 squares on the blue slab; each pulses on its own offset so the field
    # shimmers rather than blinking in unison.
    grid = "".join(f'<span style="animation-delay:{(i * 37 % 35) * 0.15:.2f}s"></span>' for i in range(35))
    tags = "".join(f"<span>{esc(m)}</span>" for m in meta)
    return f"""
    <div class="nyl-hero">
      <div class="nyl-hero__rule" aria-hidden="true"></div>
      <div class="nyl-hero__slab" aria-hidden="true"></div>
      <div class="nyl-hero__grid" aria-hidden="true">{grid}</div>
      <div class="nyl-hero__content">
        <div class="nyl-lockup">
          {logo_mark(46)}
          <span class="nyl-lockup__divider"></span>
          <span class="nyl-lockup__name">FAST Clearing Account Reconciler</span>
        </div>
        <div class="nyl-eyebrow">{esc(eyebrow)}</div>
        <div class="nyl-hero__title" role="heading" aria-level="1">{esc(title)}</div>
        <div class="nyl-hero__lede">{esc(lede)}</div>
        <div class="nyl-hero__meta">{tags}</div>
      </div>
      <div class="nyl-hero__sweep" aria-hidden="true"></div>
    </div>
    """


def chips(items: Iterable[tuple[str, str]], trusted_hint_html: str | None = None) -> str:
    """trusted_hint_html is inserted unescaped -- pass only static markup
    written in code, never anything derived from an uploaded file."""
    body = "".join(
        f'<div class="nyl-chip" style="animation-delay:{i * 0.06:.2f}s">'
        f'<div class="nyl-chip__k">{esc(k)}</div><div class="nyl-chip__v">{esc(v)}</div></div>'
        for i, (k, v) in enumerate(items)
    )
    hint = f'<div class="nyl-hint">{trusted_hint_html}</div>' if trusted_hint_html else ""
    return f'<div><div class="nyl-chips">{body}</div>{hint}</div>'


def step(number: str, title: str, hint: str = "") -> str:
    hint_html = f'<div class="nyl-step__hint">{esc(hint)}</div>' if hint else ""
    return (
        f'<div class="nyl-step"><div class="nyl-step__num">{esc(number)}</div>'
        f'<div><div class="nyl-step__title" role="heading" aria-level="2">{esc(title)}</div>{hint_html}</div></div>'
    )


def source_header(badge: str, title: str, hint: str = "") -> str:
    hint_html = f'<div class="nyl-source__hint">{esc(hint)}</div>' if hint else ""
    return (
        f'<div class="nyl-source"><div class="nyl-source__badge">{esc(badge)}</div>'
        f'<div><div class="nyl-source__title">{esc(title)}</div>{hint_html}</div></div>'
    )


def loaded(rows: int, columns: int, sheet: str | None) -> str:
    sheet_html = (
        f'<span class="nyl-loaded__dot">&middot;</span><span>sheet <b>{esc(sheet)}</b></span>' if sheet else ""
    )
    return (
        f'<div class="nyl-loaded"><span class="nyl-loaded__icon">&#10003;</span>'
        f"<span><b>{rows:,}</b> rows</span><span class=\"nyl-loaded__dot\">&middot;</span>"
        f"<span><b>{columns:,}</b> columns</span>{sheet_html}</div>"
    )


_CALLOUT_ICONS = {"info": "i", "ok": "&#10003;", "alert": "!"}


def callout(text: str, tone: str = "info") -> str:
    return (
        f'<div class="nyl-callout is-{tone}"><span class="nyl-callout__icon">{_CALLOUT_ICONS[tone]}</span>'
        f"<div>{esc(text)}</div></div>"
    )


def verdict(summary: ReconSummary, noun: str, show_population: bool = False) -> str:
    period = date_range(summary.first_date, summary.last_date)
    net = money(summary.net_difference)

    if summary.total == 0:
        tone, glyph = "info", "i"
        title = "No qualifying activity in these files."
        detail = "Every row was filtered out by the rules - check that the right sheets were selected."
    elif summary.judged == 0:
        tone, glyph = "info", "&#9670;"
        title = f"Only manual-review items in these files ({summary.manual_review})."
        detail = f"Nothing here is judged automatically · {period}"
    elif summary.all_clear:
        tone, glyph = "ok", "&#10003;"
        reconciled = f"{summary.reconciled} of {summary.judged} {plural(summary.judged, noun)} reconciled"
        if summary.manual_review:
            title = f"Reconciled - with {summary.manual_review} routed to manual review."
            detail = f"{reconciled} · {summary.manual_review} manual review · {period} · net difference {net}"
        else:
            title = f"Reconciled - every {noun} matches to the cent."
            detail = f"{reconciled} · {period} · net difference {net}"
    else:
        tone, glyph = "bad", "!"
        verb = "does" if summary.not_reconciled == 1 else "do"
        title = (
            f"Attention needed - {summary.not_reconciled} of {summary.judged} "
            f"{plural(summary.judged, noun)} {verb} not reconcile."
        )
        worst = summary.worst
        where = f"{flow_code_of(worst)} on {short_date(worst.recon_date)}" if show_population else short_date(worst.recon_date)
        detail = f"Largest gap: {where}, {money(worst.difference)} · {period} · net difference {net}"

    return _verdict(tone, glyph, title, detail)


def _verdict(tone: str, glyph: str, title: str, detail: str) -> str:
    """glyph is trusted static markup; title and detail are escaped."""
    burst = '<div class="nyl-burst" aria-hidden="true">' + "<span></span>" * 8 + "</div>" if tone == "ok" else ""
    return f"""
    <div class="nyl-verdict is-{tone}" role="status">
      <div class="nyl-verdict__mark">{glyph}{burst}</div>
      <div>
        <div class="nyl-eyebrow">Verdict</div>
        <div class="nyl-verdict__title">{esc(title)}</div>
        <div class="nyl-verdict__detail">{esc(detail)}</div>
      </div>
    </div>
    """


@dataclass(frozen=True)
class Kpi:
    label: str
    value: str
    sub: str = ""
    suffix: str = ""
    tone: str = "neutral"  # ok | bad | manual | neutral


def _kpi(index: int, k: Kpi) -> str:
    suffix = f"<small>{esc(k.suffix)}</small>" if k.suffix else ""
    return (
        f'<div class="nyl-kpi is-{k.tone}" style="animation-delay:{index * 0.07:.2f}s">'
        f'<div class="nyl-kpi__label">{esc(k.label)}</div>'
        f'<div class="nyl-kpi__value">{esc(k.value)}{suffix}</div>'
        f'<div class="nyl-kpi__sub">{esc(k.sub)}</div></div>'
    )


def kpis(items: Iterable[Kpi]) -> str:
    return f'<div class="nyl-kpis">{"".join(_kpi(i, k) for i, k in enumerate(items))}</div>'


def _diff_tone(summary: ReconSummary) -> str:
    return "ok" if summary.gross_difference == 0 else "bad"


def phase1_kpis(summary: ReconSummary, result: Phase1Result) -> list[Kpi]:
    pct = f"{summary.reconciled / summary.total:.0%}" if summary.total else "-"
    return [
        Kpi(
            "Days reconciled",
            f"{summary.reconciled}",
            suffix=f"/{summary.total}",
            sub=f"{pct} exact match" if summary.all_clear else needs_attention(summary.not_reconciled),
            tone="ok" if summary.all_clear else "bad",
        ),
        Kpi(
            "Net difference",
            money(summary.net_difference),
            sub="Across every day" if summary.gross_difference == 0 else f"Gross {money(summary.gross_difference)}",
            tone=_diff_tone(summary),
        ),
        Kpi(
            "Rows matched",
            f"{len(result.cadency_detail) + len(result.sap_detail):,}",
            sub=f"{len(result.cadency_detail):,} Cadency · {len(result.sap_detail):,} SAP",
        ),
        Kpi(
            "Period",
            f"{summary.distinct_days}",
            suffix=" days" if summary.distinct_days != 1 else " day",
            sub=date_range(summary.first_date, summary.last_date),
        ),
    ]


def phase2_kpis(summary: ReconSummary, result: Phase2Result, configured_codes: int) -> list[Kpi]:
    active = len({flow_code_of(r) for r in result.daily_results})
    return [
        Kpi(
            "Flow-code days reconciled",
            f"{summary.reconciled}",
            suffix=f"/{summary.judged}",
            sub="Every judged flow code matches" if summary.all_clear else needs_attention(summary.not_reconciled),
            tone="ok" if summary.all_clear else "bad",
        ),
        Kpi(
            "Manual review",
            f"{summary.manual_review}",
            sub="WIRE / INCO, until FAST generates them",
            tone="manual" if summary.manual_review else "neutral",
        ),
        Kpi(
            "Net difference",
            money(summary.net_difference),
            sub="Judged flow codes only" if summary.gross_difference == 0 else f"Gross {money(summary.gross_difference)}",
            tone=_diff_tone(summary),
        ),
        Kpi("Active flow codes", f"{active}", suffix=f"/{configured_codes}", sub=date_range(summary.first_date, summary.last_date)),
    ]



def phase3_verdict(result: Phase3Result) -> str:
    """Phase 3 is judged on what's left to research once DCU splits and
    timing are accounted for -- the daily table keeps the zero-tolerance
    day-by-day status, but most of those days are explained timing."""
    dates = sorted(r.recon_date for r in result.daily_results)
    period = date_range(dates[0], dates[-1]) if dates else ""
    items = result.exceptions
    diff = money(result.difference)

    if not result.daily_results:
        return _verdict(
            "info", "i", "No reclaim activity in these files.",
            "No RCCR reclaims in the Cadency file and no +166 lines in the Treasury file - check the sheets selected.",
        )
    if not items and result.difference == 0:
        return _verdict(
            "ok", "&#10003;", "Reconciled - every reclaim is accounted for.",
            f"{result.days_same_day} {plural(result.days_same_day, 'day')} tie the same day, "
            f"{result.days_timing} after timing · {period} · month difference {diff}",
        )
    left = (
        "nothing left unexplained" if result.unexplained == 0 else f"{money(result.unexplained)} still unexplained"
    )
    return _verdict(
        "bad", "!", f"Attention needed - {len(items)} {plural(len(items), 'item')} to research.",
        f"Month difference {diff} · {money(result.explained)} explained by the items below · {left} · {period}",
    )


def phase3_kpis(result: Phase3Result) -> list[Kpi]:
    items = result.exceptions
    days = result.days_same_day + result.days_timing + result.days_with_exceptions
    dcu = result.dcu_status_counts()
    for_account = dcu["applied"] + dcu["not_applied"]
    dcu_sub = f"{money(result.dcu_split_total)} split out"
    if dcu["ignored"]:
        dcu_sub += f" · {dcu['ignored']} other-account {plural(dcu['ignored'], 'row')} ignored"
    return [
        Kpi(
            "Items to research",
            f"{len(items)}",
            sub="After DCU splits and timing" if items else "Nothing left to research",
            tone="bad" if items else "ok",
        ),
        Kpi(
            "Month difference",
            money(result.difference),
            sub="Bank vs. Cadency net of DCU"
            if result.difference == 0
            else ("Fully itemised below" if result.unexplained == 0 else f"{money(result.unexplained)} unexplained"),
            tone="ok" if result.difference == 0 else ("neutral" if result.unexplained == 0 else "bad"),
        ),
        Kpi(
            "Cadency days tied",
            f"{result.days_same_day + result.days_timing}",
            suffix=f"/{days}",
            sub=f"{result.days_same_day} same day · {result.days_timing} after timing",
            tone="ok" if days and not result.days_with_exceptions else "neutral",
        ),
        Kpi(
            "DCU splits applied",
            f"{dcu['applied']}",
            suffix=f"/{for_account}",
            sub=dcu_sub,
            tone="bad" if dcu["not_applied"] else "neutral",
        ),
    ]


def bridge(result: Phase3Result, account_number: str) -> str:
    """Cadency's full reclaims down to the bank, one line at a time -- the
    month's arithmetic, so the verdict's numbers can be checked by eye."""
    rows = [
        ("Cadency reclaim credits, full amount", result.cadency_full_total, ""),
        ("Less DCU splits to other accounts", -result.dcu_split_total, ""),
        (f"Expected in {account_number}", result.expected_total, "is-total"),
        (f"Bank {result.flow_code} receipts", result.bank_total, ""),
        ("Difference (bank - expected)", result.difference, "is-total"),
        ("Itemised in the research below", result.explained, ""),
        ("Still unexplained", result.unexplained, "is-ok" if result.unexplained == 0 else "is-bad"),
    ]
    body = "".join(
        f'<div class="nyl-bridge__row {cls}"><span>{esc(label)}</span><span>{esc(money(value))}</span></div>'
        for label, value, cls in rows
    )
    return f"""
    <div class="nyl-panel">
      <div class="nyl-eyebrow">The month, step by step</div>
      <div class="nyl-panel__title">From Cadency's full reclaims to the bank</div>
      <div class="nyl-bridge">{body}</div>
    </div>
    """


def legend() -> str:
    return (
        '<div class="nyl-legend">'
        f"<span>{_sq('RECONCILED')}Reconciled</span>"
        f"<span>{_sq('DOES NOT RECONCILE')}Does not reconcile</span>"
        f"<span>{_sq('MANUAL REVIEW')}Manual review</span>"
        "</div>"
    )


def _tooltip(r: DailyResult) -> str:
    return (
        f"{r.recon_date:%a} {short_date(r.recon_date)} · {r.status.value} · "
        f"{r.source_a_label} {money(r.source_a_total)} · {r.source_b_label} {money(r.source_b_total)} · "
        f"difference {money(r.difference)}" + (f" · {r.note}" if r.note else "")
    )


def heartbeat(daily_results: list[DailyResult]) -> str:
    """One square per day, grouped by month -- the whole period at a glance."""
    by_month: dict[tuple[int, int], list[DailyResult]] = {}
    for r in sorted(daily_results, key=lambda r: r.recon_date):
        by_month.setdefault((r.recon_date.year, r.recon_date.month), []).append(r)

    months, i = [], 0
    for (year, month), days in by_month.items():
        cells = []
        for r in days:
            cells.append(
                f'<div class="nyl-beat__day" style="animation-delay:{min(i, 60) * 0.025:.3f}s">'
                f"{_sq(r.status.value, _tooltip(r))}"
                f'<span class="nyl-beat__d">{r.recon_date.day}</span>'
                f'<span class="nyl-beat__w">{r.recon_date:%a}</span></div>'
            )
            i += 1
        label = date(year, month, 1).strftime("%B %Y")
        months.append(f'<div><div class="nyl-beat__mlabel">{label}</div><div class="nyl-beat">{"".join(cells)}</div></div>')

    return f"""
    <div class="nyl-panel">
      <div class="nyl-panel__head">
        <div><div class="nyl-eyebrow">Daily heartbeat</div>
          <div class="nyl-panel__title">Every day in the period, at a glance</div></div>
        {legend()}
      </div>
      <div class="nyl-beat__months">{"".join(months)}</div>
    </div>
    """


def _rule_label(rule: FlowCodeRule) -> str:
    detail = f"{rule.cadency_ref10} / {' + '.join(rule.cadency_trans_type_codes)}"
    if rule.reference7_equals:
        detail += f" / Ref 7 = {rule.reference7_equals}"
    return detail


def status_matrix(daily_results: list[DailyResult], rules: list[FlowCodeRule]) -> str:
    """Flow codes down the side, days across the top -- each flow code
    reconciles independently, so every cell stands on its own."""
    dates = sorted({r.recon_date for r in daily_results})
    cells = {(flow_code_of(r), r.recon_date): r for r in daily_results}

    head = ['<div class="nyl-matrix__corner">Flow code</div>']
    prev_month = None
    for d in dates:
        month = f"<small>{d:%b}</small>" if d.month != prev_month else "<small>&nbsp;</small>"
        prev_month = d.month
        head.append(f'<div class="nyl-matrix__col">{month}{d.day}</div>')

    rows, i = [], 0
    for rule in rules:
        rows.append(
            f'<div class="nyl-matrix__row" title="{esc(rule.notes)}">'
            f'<span class="nyl-matrix__code">{esc(rule.flow_code)}</span>'
            f'<span class="nyl-matrix__note">{esc(_rule_label(rule))}</span></div>'
        )
        for d in dates:
            r = cells.get((rule.flow_code, d))
            delay = min(i, 80) * 0.012
            if r:
                rows.append(_sq(r.status.value, _tooltip(r), delay))
            else:
                rows.append(_sq(None, f"{rule.flow_code} · {short_date(d)} · no activity", delay))
            i += 1

    columns = f"grid-template-columns: minmax(170px, max-content) repeat({len(dates)}, 28px)"
    return f"""
    <div class="nyl-panel">
      <div class="nyl-panel__head">
        <div><div class="nyl-eyebrow">Status matrix</div>
          <div class="nyl-panel__title">Each flow code, each day - reconciled independently</div></div>
        {legend()}
      </div>
      <div class="nyl-matrix-wrap"><div class="nyl-matrix" style="{columns}">{"".join(head)}{"".join(rows)}</div></div>
    </div>
    """


def facts(items: Iterable[tuple[str, str]]) -> str:
    body = "".join(f'<div class="nyl-facts__k">{esc(k)}</div><div class="nyl-facts__v">{esc(v)}</div>' for k, v in items)
    return f'<div class="nyl-facts">{body}</div>'


def export_panel(sheet_names: Iterable[str], filename: str) -> str:
    names = list(sheet_names)
    stack = "<span></span>" * len(names)
    tabs = "".join(f"<span>{esc(n)}</span>" for n in names)
    return f"""
    <div class="nyl-export">
      <div class="nyl-export__stack" aria-hidden="true">{stack}</div>
      <div>
        <div class="nyl-export__title">{len(names)}-tab Excel workbook, color-coded and ready for review</div>
        <div class="nyl-export__tabs">{tabs}</div>
        <div class="nyl-export__file">{esc(filename)}</div>
      </div>
    </div>
    """


def phase_card(number: str, title: str, description: str, status: str | None, status_label: str, delay: float = 0) -> str:
    square = _sq(status) if status else '<span class="nyl-sq is-empty"></span>'
    return f"""
    <div class="nyl-phase" style="animation-delay:{delay:.2f}s">
      <div class="nyl-phase__num">{esc(number)}</div>
      <div class="nyl-phase__title">{esc(title)}</div>
      <div class="nyl-phase__desc">{esc(description)}</div>
      <div class="nyl-phase__status">{square}{esc(status_label)}</div>
    </div>
    """


def legacy_card(account_label: str, flow_code: str, trans_type: str, title: str, description: str) -> str:
    return f"""
    <div class="nyl-legacy">
      <div class="nyl-legacy__acct">{esc(account_label)}</div>
      <div class="nyl-legacy__link"><span class="nyl-matrix__code">{esc(flow_code)}</span>
        <span class="nyl-legacy__arrow">&#8644;</span><span class="nyl-matrix__code">{esc(trans_type)}</span></div>
      <div class="nyl-phase__title">{esc(title)}</div>
      <div class="nyl-phase__desc">{esc(description)}</div>
    </div>
    """


def roadmap(items: Iterable[tuple[str | None, str, str]]) -> str:
    """(status, title, detail) per milestone; status None = not started."""
    body = "".join(
        f'<div class="nyl-road__item" style="animation-delay:{i * 0.08:.2f}s">{_sq(status) if status else _sq(None)}'
        f'<div><div class="nyl-road__t">{esc(title)}</div><div class="nyl-road__d">{esc(detail)}</div></div></div>'
        for i, (status, title, detail) in enumerate(items)
    )
    return f'<div class="nyl-panel"><div class="nyl-eyebrow">Roadmap</div><div class="nyl-road">{body}</div></div>'


def how_it_works() -> str:
    steps = [
        ("Load the raw exports", "Cadency, SAP and the bank statement exactly as they're downloaded - no pre-filtering, no pivot tables."),
        ("The rules do the sorting", "Each row is routed by Reference 10, Reference 9 and Reference 7 into the population it belongs to."),
        ("Get an exact-match verdict", "Every day and every flow code is judged to the cent, with a color-coded Excel workbook to prove it."),
    ]
    body = "".join(
        f'<div class="nyl-flow__step" style="animation-delay:{i * 0.1:.1f}s"><div class="nyl-flow__n">{i + 1}</div>'
        f'<div class="nyl-flow__t">{esc(t)}</div><div class="nyl-flow__d">{esc(d)}</div></div>'
        for i, (t, d) in enumerate(steps)
    )
    return f'<div class="nyl-flow">{body}</div>'


def _initials(name: str) -> str:
    return "".join(part[0] for part in name.split()[:2]).upper()


def credit_banner() -> str:
    return f"""
    <div class="nyl-credit">
      <div class="nyl-avatar" aria-hidden="true">{esc(_initials(BUILT_BY))}</div>
      <div class="nyl-credit__body">
        <div class="nyl-eyebrow">Designed &amp; built by</div>
        <div class="nyl-credit__name">{esc(BUILT_BY)}</div>
      </div>
    </div>
    """


def profile_card() -> str:
    return f"""
    <div class="nyl-profile">
      <div class="nyl-eyebrow">Built by</div>
      <div class="nyl-profile__row">
        <div class="nyl-avatar" aria-hidden="true">{esc(_initials(BUILT_BY))}</div>
        <div class="nyl-profile__name">{esc(BUILT_BY)}</div>
      </div>
    </div>
    """


def footer() -> str:
    return f"""
    <div class="nyl-footer">
      <div class="nyl-footer__brand">
        {logo_mark(52)}
        <div><div class="nyl-footer__company">New York Life Insurance Company</div>
          <div class="nyl-footer__small">For internal use only.</div></div>
      </div>
      <div class="nyl-footer__credit">Built by <b>{esc(BUILT_BY)}</b></div>
      <div class="nyl-footer__contact">Questions? Contact {esc(BUILT_BY)}</div>
    </div>
    """
