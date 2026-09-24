# FAST Clearing Account Reconciler — Shell

A Streamlit prototype for the daily FAST reconciliation tool described in
Sean Kelly's Accounting Reconciliation Business Requirements doc, the
Cadency-to-SAP Monthly Trial Balance Procedure doc, and the CODA project
meeting notes. **Note on direction:** both of those docs name an
Excel/Power Query build as the officially proposed solution; this Streamlit
app is exploratory/fallback work, not (yet) the agreed deliverable — see
the CODA meeting notes' "Recommended Direction" section.

**This is a shell, not a finished tool** — Phase 1 and Phase 2 are real and
tested; Phase 3 is still a stubbed page that shows the config already
captured for it.

## What's built vs. stubbed

| Phase | Status | What it does |
|---|---|---|
| Phase 1 — FAST vs. SAP | **Built & tested** | Aggregate, exact-match, daily. See `core/matching.py::run_phase1`. |
| Phase 2 — Treasury Flow Codes | **Built & tested** | Each Flow Code reconciles independently, daily, against its own Cadency population, incl. the -466 effective-date exception and -495/+195 manual review. See `core/matching.py::run_phase2`. |
| Phase 3 — Reclaim netting (Accts 187/147) | Stub | Page shows the legacy account mapping already defined in config; no netting logic yet. |

## Project layout

```
app.py                          Streamlit home page — account selector, file inputs, runs Phase 1
app.yaml                        Databricks Apps run config
requirements.txt
core/
  config.py                     AccountConfig / FlowCodeRule registry — the reuse layer (see below)
  schema.py                     Column-name resolution, incl. one still-open assumption (see below)
  io_utils.py                   Loads a source from either an upload or a Databricks Volume path; lists sheet names for the picker
  ui.py                         Shared Streamlit widgets (file input + sheet picker, color-coded results table)
  matching.py                   run_phase1 / run_phase2 (built); run_phase3 (stub)
  models.py                     DailyResult / Phase1Result / Phase2Result dataclasses
  export.py                     Excel export -- see "Excel export" below
pages/
  1_Phase_2_Treasury_Match.py   Built — Treasury/bank Flow Code matching
  2_Phase_3_Reclaims.py         Stub page
tests/
  test_phase1_matching.py       Unit tests for run_phase1 (stdlib unittest, no extra deps)
  test_phase2_matching.py       Unit tests for run_phase2, incl. -466/-GDSCK_* Reference 7 split and manual review
  test_export.py                Unit tests for export_workbook (sheet names, content, status color-fill)
  test_io_utils.py              Unit tests for list_sheet_names / load_tabular (multi-sheet workbook handling)
sample_data/
  sample_cadency_export.csv     Synthetic data — NOT real transactions — covers Phase 1 + Phase 2 Flow Codes
  sample_sap_export.csv         Synthetic data — includes one intentional mismatch day
  sample_bank_export.csv        Synthetic data — includes one intentional $10 mismatch (+GDSCK_S)
  sample_multi_sheet_workbook.xlsx  Synthetic data — same Cadency/SAP rows, split into two named tabs ("Cadency match to SAP" / "SAP Match to Cadency") to test the sheet picker
```

## Running locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Try it against `sample_data/` first: upload both sample files on the home
page and click **Run Phase 1 Reconciliation**. You should see two
`RECONCILED` days (8/3, 8/4) and one `DOES NOT RECONCILE` day (8/5, off by
$50) — that's intentional, to show both states render correctly.

For Phase 2, go to the **Phase 2 - Treasury Match** page in the sidebar and
upload `sample_cadency_export.csv` and `sample_bank_export.csv`. You should
see six `RECONCILED` Flow Codes, one `DOES NOT RECONCILE` Flow Code
(`+GDSCK_S`, off by $10 — intentional), and `-495`/`+195` both flagged
`MANUAL REVIEW` regardless of whether the amounts happen to match.

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
into either the Cadency or SAP slot on the home page and you'll get the
sheet picker with `Cadency match to SAP` / `SAP Match to Cadency` as
options. `demo.html` has the same picker (upload it there in either the
Phase 1 or Phase 2 tab to see it live in the browser mockup, no Streamlit
needed).

## Excel export

Each phase's page has a **Download Excel export** button (`core/export.py`)
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

**2. The actual Treasury/bank export layout.** No real bank/treasury
statement file has been provided yet — `core/schema.py`'s
`Flow Code` / `Date` / `Amount` column names are a working assumption
inferred from Sean's July 2026 manual working file, not a raw export.
Given the SAP amount-column miss above, don't assume this one is right
either — confirm against a real export before Phase 2 is trusted in
production.

## Other things still open per the meeting notes / business docs (not shell-blocking, but worth tracking)

- **Monthly Final Roundup** — the Business Requirements doc calls this out
  as a *separate, secondary* control from the daily Phase 1–3 reconciliation
  (validates Cadency's monthly balance vs. SAP's monthly Trial Balance,
  after legacy-account activity). Its methodology is marked TBD and it
  isn't represented anywhere in this shell yet (no Phase 4 / monthly page).
- **Account 187 trigger condition** — it's a conditional input, not a daily
  one, but *when* it's required still isn't documented.
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
