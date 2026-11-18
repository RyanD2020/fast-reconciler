# FAST Clearing Account Reconciler — Shell

Built by **Ryan Doswell**

A Streamlit prototype for the daily FAST reconciliation tool described in
Sean Kelly's Accounting Reconciliation Business Requirements doc, the
Cadency-to-SAP Monthly Trial Balance Procedure doc, and the CODA project
meeting notes. **Note on direction:** both of those docs name an
Excel/Power Query build as the officially proposed solution; this Streamlit
app is exploratory/fallback work, not (yet) the agreed deliverable — see
the CODA meeting notes' "Recommended Direction" section.

**This is a shell, not a finished tool** — Phase 1 and Phase 2 are real and
tested; Phase 3 is built and tested for reclaim credits (+166), with reclaim
debits (-468) still waiting on test data.

## What's built vs. stubbed

| Phase | Status | What it does |
|---|---|---|
| Phase 1 — FAST vs. SAP | **Built & tested** | Aggregate, exact-match, daily. See `core/matching.py::run_phase1`. |
| Phase 2 — Treasury Flow Codes | **Built & tested** | Each Flow Code reconciles independently, daily, against its own Cadency population, incl. the -466 effective-date exception and -495/+195 manual review. See `core/matching.py::run_phase2`. |
| Phase 3 — Reclaim credits (+166, Acct 187) | **Built & tested** | Cadency RCCR reclaims net of DCU's splits to other accounts, matched daily to bank +166, with timing research that isolates what's left to look into. See `core/matching.py::run_phase3` and [Phase 3](#phase-3--reclaim-credits-net-of-dcu-splits). |
| Phase 3 — Reclaim debits (-468, Acct 147) | Not started | No test data yet. |

## Project layout

```
app.py                          Entrypoint + router (st.navigation): theme, sidebar, footer shared by every page
app.yaml                        Databricks Apps run config
requirements.txt
views/
  overview.py                   Landing page: live status of each phase this session, how it works, credits
  phase1.py                     Phase 1 - FAST vs. SAP
  phase2.py                     Phase 2 - Treasury / bank Flow Codes
  phase3.py                     Phase 3 - reclaim credits net of DCU splits, with timing research
core/
  config.py                     AccountConfig / FlowCodeRule registry — the reuse layer (see below)
  schema.py                     Column-name resolution, incl. one still-open assumption (see below)
  io_utils.py                   Loads a source from either an upload or a Databricks Volume path; lists sheet names for the picker
  matching.py                   run_phase1 / run_phase2 / run_phase3 (incl. DCU split matching)
  timing.py                     Phase 3 timing research: which bank lines pay for which Cadency day (pure Python)
  models.py                     DailyResult / Phase1Result / Phase2Result / Phase3Result dataclasses
  export.py                     Excel export -- see "Excel export" below
  insights.py                   Run summaries behind the verdict, KPI tiles and "Run details" (Streamlit-free)
  brand.py                      NYL colors, fonts, status glyphs, credits -- single source of truth
  theme.py                      The stylesheet, built from brand.py (Streamlit-free)
  components.py                 HTML building blocks: hero, verdict, KPI tiles, heartbeat, status matrix... (Streamlit-free)
  ui.py                         Thin Streamlit glue: file inputs + sheet picker, Run button persistence, workbook download
tests/
  test_phase1_matching.py       Unit tests for run_phase1 (stdlib unittest, no extra deps)
  test_phase2_matching.py       Unit tests for run_phase2, incl. -466/-GDSCK_* Reference 7 split and manual review
  test_phase3_matching.py       Unit tests for run_phase3: DCU splits, ignored accounts, a whole synthetic month
  test_timing.py                Unit tests for the timing research (same-day, next-day, runs, set-aside, unclaimed)
  test_export.py                Unit tests for export_workbook (sheet names, content, status color-fill)
  test_io_utils.py              Unit tests for list_sheet_names / load_tabular (multi-sheet workbook handling)
  test_schema.py                Unit tests for column resolution (real SAP layout, TA vs. Amount priority)
  test_insights.py              Unit tests for the verdict / KPI math
  test_components.py            Unit tests for the UI HTML: escaping of uploaded text, verdict wording, markup shape
sample_data/
  sample_cadency_export.csv     Synthetic data — NOT real transactions — covers Phase 1 + Phase 2 Flow Codes
  sample_sap_export.csv         Synthetic data — includes one intentional mismatch day
  sample_bank_export.csv        Synthetic data — includes one intentional $10 mismatch (+GDSCK_S)
  sample_multi_sheet_workbook.xlsx  Synthetic data — same Cadency/SAP rows, split into two named tabs ("Cadency match to SAP" / "SAP Match to Cadency") to test the sheet picker
  sample_phase3_cadency_reclaims.csv  Synthetic data — RCCR reclaims (plus one non-reclaim row to be filtered out)
  sample_phase3_bank_export.csv       Synthetic data — headerless Treasury layout, +166 lines, one +301 line and a footer row
  sample_phase3_dcu_reclaims.csv      Synthetic data — one DCU split for 19803075, one for another account (ignored)
```

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

The app opens on **Overview**. Try it against `sample_data/` first: open
**Phase 1 · FAST vs. SAP** in the sidebar, upload both sample files and click
**Run Phase 1 reconciliation**. You should see two `RECONCILED` days (8/3,
8/4) and one `DOES NOT RECONCILE` day (8/5, off by $50) — that's
intentional, to show both states render correctly. The sample Cadency file
mirrors a real export's layout: an unsigned `Amount` column plus the signed
`TA` column the reconciliation actually uses.

For Phase 2, open **Phase 2 · Treasury** in the sidebar and
upload `sample_cadency_export.csv` and `sample_bank_export.csv`. You should
see six `RECONCILED` Flow Codes, one `DOES NOT RECONCILE` Flow Code
(`+GDSCK_S`, off by $10 — intentional), and `-495`/`+195` both flagged
`MANUAL REVIEW` regardless of whether the amounts happen to match.

For Phase 3, open **Phase 3 · Reclaims** and load the three
`sample_phase3_*.csv` files (Cadency, Treasury, DCU). You should see
**2 items to research** that fully explain the month's $161.12 difference:
a $88.88 reclaim on 9/3 with no bank receipt, and a $250.00 bank line on
9/10 with no reclaim behind it. 9/1 and 9/8–9/9 tie once timing is counted;
the $300.00 DCU split comes off the 9/1 reclaim; the 19803095 DCU row is
ignored.

## Phase 3 — reclaim credits net of DCU splits

From Sean's email of 2026-11-18 and his `Phase 3 Test Data.xlsx` (three
tabs: September RCCR items from Cadency, the +166 bank lines, and DCU's
reclaims sheet). When reclaim funds are split between accounts, Cadency
books the **full** reclaim to 19803075 and the other account's share
(Account 187) is moved at month end, so Cadency can carry more than this
account's bank ever receives. DCU's sheet says how much of which reclaim
went elsewhere.

1. **Cadency side** — Reference 10 = FAST, Reference 9 = RCCR, full signed
   amount (`TA` / `True Amount`), by Post Date. A full Cadency export works
   too; everything else is filtered out.
2. **DCU splits** — each DCU row for **this** account (the `Acct#` column)
   is matched to one reclaim on Certificate Number = Cadency **Reference 4**,
   confirmed by Contract Number = the digits of **Reference 2** (`GA01234` ↔
   1234), and subtracted from it. Rows for other accounts (e.g. 19803095)
   are ignored, per Sean. A row is *not* applied, and is listed as an item
   to research, if it can't be matched safely: no matching reclaim,
   certificate matches but contract doesn't, more than one candidate, or a
   split bigger than the reclaim.
3. **Daily compare** — bank +166 vs. Cadency net of DCU, per day, zero
   tolerance, same as Phases 1 and 2.
4. **Timing research** (`core/timing.py`) — the bank receives reclaims in
   batches that land a day either side of the Cadency post date, so most
   days don't tie on their own. For each day the tool looks for the exact
   combination of bank lines, within one activity day either side, that
   ties to the cent; then tries neighbouring days together; then checks
   whether the day ties once a single reclaim is set aside. What's left
   is reported as items to research. This never changes a day's status;
   it writes the day's note and the **Items to research** list.

The page leads with a verdict on the items to research and a step-by-step
bridge: Cadency full amount → less DCU splits → expected → bank →
difference → itemised → still unexplained.

**Against Sean's September 2026 test data** (real data — not in the repo,
and no figures from it are quoted here): a strict daily compare
reconciles 1 of 16 days. Once DCU's two splits for this account are
applied and timing is counted, 11 of the 14 Cadency days tie exactly, and
the month's whole difference comes down to three items — the same three
Sean had annotated in the bank tab by hand (two "suppression" reclaims
with no bank receipt, and one bank line with no reclaim behind it).
Nothing is left unexplained.

**Still to confirm for Phase 3:**

- **DCU match key.** Reference 4 = certificate and Reference 2 = "GA" +
  contract number holds for both DCU rows in the test data, but it was
  read from the data, not confirmed.
- **Timing window.** One activity day either side fits all of the
  September data. Confirm that's acceptable (and whether a longer lag
  should ever count as timing). Set per account in
  `AccountConfig.phase3_timing_window_days`.
- **"Suppression".** Sean's notes mark the two reclaims without a bank
  receipt as suppressions. If suppressions are known up front (a list or
  a flag), they could be an input and drop out of the research list.
- **DCU `Acct#` = 147.** The header lists 147 as a possible value. Today
  any account other than this one is ignored; confirm what a 147 row
  means for the credit side.
- **Sean's example arithmetic.** The worked example in his email has a
  subtraction slip; the correctly subtracted figure is the one that ties
  to the bank.
- **Reclaim debits (-468 / RCDB / Account 147)** need their own test data.

`demo.html` (the static browser mockup) has not been updated for Phase 3.

## Loading multi-sheet workbooks

Every file upload / Volume-path input (Cadency, SAP, bank) checks how many
sheets the file has. A single-sheet file (or a `.csv`) loads with no extra
step. A multi-sheet workbook — e.g. someone's own manual review file with
several tabs — shows a "Which sheet is [source]?" dropdown instead of
silently grabbing the first sheet. Per Sean (2026-09-23): live/production
exports are expected to stay raw single-purpose files with minimal
pre-manipulation, so this picker is mainly a safety net for exactly the
case it was built for — someone uploading an already-organized review
workbook and needing to point the tool at the right tab. Whatever sheet is
selected still goes through the normal Phase 1 / Phase 2 filtering logic;
nothing about this input path skips or trusts pre-filtered data.

Try it against `sample_data/sample_multi_sheet_workbook.xlsx` — upload it
into either the Cadency or SAP slot on the Phase 1 page and you'll get the
sheet picker with `Cadency match to SAP` / `SAP Match to Cadency` as
options. `demo.html` has the same picker (upload it there in either the
Phase 1 or Phase 2 tab to see it live in the browser mockup, no Streamlit
needed).

## NYL brand theme

Both the real app and `demo.html` use the NYL brand palette (`core/brand.py`
is the Python source of truth; `demo.html`'s `<style>` block mirrors it
manually, same pattern as the schema.py column-candidate lists): Dark Blue
`#000A62` for primary surfaces/headlines/buttons, Blue `#0468FF` for the
logo mark/eyebrow labels/section markers, Green `#016355` for
RECONCILED/PASS states, White and `#E3E0DD` Grey as the only background
colors, Georgia for headlines and Arial for body/UI text, no rounded
corners, no shadows, no gradients.

**One deliberate deviation from a literal brand reading:** the original
results table used colored row *backgrounds* (green/red/yellow) for
RECONCILED/DOES NOT RECONCILE/MANUAL REVIEW. The brand palette has no
red or yellow, and specifies white/grey as the *only* background colors —
so status is now shown via bold colored **text** instead (Green /
Dark Blue / Blue — Dark Blue standing in as the most severe color for
DOES NOT RECONCILE, since there's no red to reach for), on plain
white/grey rows. Revisit this if NYL brand guidance ever adds a defined
"fail" or "warning" color.

**A second deliberate deviation:** numerals (KPI values, step and phase
numbers) are set in Arial, not Georgia. Georgia only has old-style figures,
where "0" is an x-height circle, so "$0.00" renders as "$o.oo" — not
acceptable for the one number this tool exists to show. Georgia stays on
every headline, title and verdict.

No official NYL logo file was available — the logo mark (blue square,
stacked "NEW YORK LIFE") is recreated in HTML/CSS from a reference image,
not an official asset. Swap `core/components.py::logo_mark` (and
`demo.html`'s `.logo-mark`) for a real `<img>`/`<svg>` once one exists.

## The interface

- **Navigation** (`st.navigation` in `app.py`): Overview, then Phase 1 / 2 /
  3, with one shared account selector and the credits card in the sidebar.
- **Hero** on every page: the NYL diagonal-mask motif (Dark Blue field, steep
  white rule, Blue slab) with a field of squares that shimmers gently.
- **Verdict banner**: one sentence that answers "did it reconcile?", naming
  the largest gap when it didn't.
- **KPI tiles**, a **daily heartbeat** (one square per day, Phase 1) and a
  **status matrix** (flow codes x days, Phase 2). Status is never color
  alone — every square carries a glyph (✓ / ✕ / ◆) and a hover tooltip, and
  the same numbers are in the "Daily results" table.
- **Run details** tab: which columns resolved, which sign convention was
  applied, how many rows survived the rules — so a surprising total can be
  traced without reading code.
- All motion switches off under the OS "reduce motion" setting.

Everything visual is built by Streamlit-free modules (`core/theme.py`,
`core/components.py`, `core/insights.py`) and unit-tested; `core/ui.py` is
only the thin Streamlit glue. Dynamic text from uploaded files (sheet names,
column headers, error messages) is HTML-escaped before rendering.

## Performance

Streamlit reruns the whole page on every click, so two expensive steps are
deliberately kept out of the rerun path (measured on a real month, 95K
Cadency rows):

- **Reading the files (~13s)** is cached on the file's bytes
  (`st.cache_data`), so it happens once per upload, not once per click.
- **Building the Excel workbook (~73s)** happens only when you click
  **Prepare Excel workbook**, once per run, then the Download button reuses
  it. The pages used to rebuild it on every rerun, which made each click
  stall for over a minute — the likely real cause of the "going dark"
  behavior seen on Databricks.

## Results survive a dropped/reconnected session

Both Phase 1 and Phase 2 persist their results in `st.session_state`
(`core/ui.py::run_with_persistence`) rather than only displaying them for
the one script run where the Run button was clicked. Without this,
Streamlit's rerun model meant results would vanish and require re-clicking
Run after *any* rerun — including a websocket reconnect (e.g. Databricks
Apps' proxy dropping an idle connection during a long review session) or
even just clicking the Download Excel button, since every Streamlit button
triggers a full script rerun. Results are keyed to the selected account, so
switching accounts clears the old ones rather than showing stale numbers
under a different account's label.

## Excel export

Each phase's page has a **Prepare Excel workbook** / **Download Excel workbook** pair (`core/export.py`)
that packages the run into a single `.xlsx`, shaped to match the workbook
Sean already builds by hand for his monthly review — the intent is that
this can slot into his existing process rather than replace it with
something unfamiliar:

1. **Results** — the daily/per-Flow-Code compare, color-coded
   RECONCILED/DOES NOT RECONCILE/MANUAL REVIEW. This is the actual
   improvement over the manual version: an automated pass/fail instead of
   eyeballing two totals.
2. **Cadency - Phase N Qualifying** / **SAP or Bank - Phase N Qualifying** —
   the same filtered tabs Sean's sheet already has (his Tab 1 / Tab 2).
3. **Cadency - Raw** / **SAP or Bank - Raw** — the source file exactly as
   uploaded, unfiltered (his Tab 3), for backup/reference.

## Running the tests

```bash
python -m unittest discover -s tests -v
```

## Deploying to Databricks Apps

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for the full runbook — prerequisites,
CLI steps, and what's confirmed vs. assumed in `app.yaml` /
`.streamlit/config.toml`. Short version: **I don't have a sample of your
org's existing Databricks Apps setup to match conventions against** — check
it against however other apps in your workspace are configured (service
principal, secret scopes, env vars) before deploying.

## Adding a new account (the reuse layer)

Per the CODA meeting notes, the long-term goal is ~20 accounts, not just
19803075. To onboard another account, add a new entry to
`core.config.ACCOUNTS` — the matching engine in `core/matching.py` reads
everything (Reference 10 values, qualifying Trans Types, SAP Text values,
Flow Codes, legacy account numbers) from that config rather than hardcoding
anything account-specific. Phase 1 should work for a new account without
touching `matching.py` at all.

## Resolved since the last round (via real source files added 2026-09-23)

**Which column actually holds the Cadency trans-type code — resolved: Reference 9.**
`Cadency_Export_Guide.xlsx`'s idealized sample sheet has a dedicated `TR No`
column, but the real `July 2026 19803075.xlsx` → `Sheet1` export has no
`TR No` or `True Amount` column at all — just generic `Reference 2`–
`Reference 9`, with `Reference 9` holding the code (e.g. `OVER`). Both the
Business Requirements doc and the Monthly SAP Trial Balance Procedure doc
also consistently call this column "Cadency Transaction Type - Ref 9."
`core/schema.py` now expects `Reference 9` first and falls back to `TR No`
only for the idealized format, still raising if a file somehow has both.

**The SAP export layout — resolved: it's a real SAP GL line-item export.**
Confirmed 2026-09-24 the hard way: `demo.html`'s naive column matching
silently reported every SAP row as `$0` before it had the same defensive
check as `core/schema.py`. The real file uses the classic SAP FI
display-document field set (`Document Type`, `Posting Key`, `Clearing
Document`, `Profit Center`, `Offsetting Account`, etc.) — `Text` and
`Document Date` are exactly as assumed, but the amount column is
**`Amount in Local Currency`**, not `Local Currency Amount` as originally
guessed (same words, different order). `SAP_AMOUNT_COLUMN_CANDIDATES` now
includes the real name; see `core/schema.py`'s docstring and
`tests/test_schema.py` for the regression test.

## Open items to confirm before this goes further

**1. Is "5801" an exact code or a range?** `Cadency_Export_Guide.xlsx`'s
`"FAST TR NO's"` reference sheet describes it as *"TR 5801 through 5905 —
Benefit Payments & Lump Sum Benefits,"* and doesn't list `OVER` at all — but
the Business Requirements doc and the real export both use exact `"5801"`
and `"OVER"` as literal codes. If real Cadency data actually contains
sub-codes like 5802–5905, `core/config.py`'s exact-match Phase 1 code list
would silently under-count the Cadency side. **Confirm with Sean before
trusting Phase 1 against a full month of real data.**

**2. The actual Treasury/bank export layout — resolved (2026-10-27, 2026-11-18).**
The real export is headerless (Date / Bank ID / Account / Amount / Flow
Code, then a footer row); see `core/schema.py` item 4. Sean's Phase 3 bank
tab added two variants, both handled: a blank first row, and a code
column where every value is "+166" (pandas reads that as the number 166).
Before this, that tab failed to load in Phase 2 as well.

## Other things still open per the meeting notes / business docs (not shell-blocking, but worth tracking)

- **Monthly Final Roundup** — the Business Requirements doc calls this out
  as a *separate, secondary* control from the daily Phase 1–3 reconciliation
  (validates Cadency's monthly balance vs. SAP's monthly Trial Balance,
  after legacy-account activity). Its methodology is marked TBD and it
  isn't represented anywhere in this shell yet (no Phase 4 / monthly page).
- **Account 187 trigger condition** — answered by Sean (2026-11-18): Account
  187 comes in when reclaim funds are split between accounts, and DCU's
  reclaims sheet is the notification. Phase 3 consumes that sheet.
- **Account 147's existing reconciliation** — `Acct 147 Rec January 2024.xlsx`
  shows Account 147 already has its own large, separate, mature daily
  reconciliation (SAP account 19801750, ~800-code Flow Code dictionary).
  Phase 3 should consume a manually-provided extract of the RCDB-attributable
  slice of that activity, not try to reproduce it.
- **SUSP** — a new transaction type expected in a future sprint; worth using
  as the first real test of whether the config-driven approach makes adding
  a transaction type actually easy.
- **Ownership** — rules vs. hosting vs. defect-fix vs. deployment ownership
  is still an open leadership question (Umar was named as the contact).
- **Direction tension** — both the CODA meeting notes and Sean's own
  Business Requirements doc name Excel + Power Query as the *proposed*
  solution, with Streamlit as a fallback "if Excel proves insufficient."
  Worth being clear internally about whether this shell is that fallback
  being built in parallel, or a decision to go this route instead.
