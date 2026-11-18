"""
Column-name resolution for the raw source files.

1. CADENCY TRANS-TYPE CODE COLUMN -- CONFIRMED
   Real production Cadency exports (July 2026 19803075.xlsx -> Sheet1) have
   no "TR No" or "True Amount" column -- just generic Reference 2 through
   Reference 9, with Reference 9 holding the trans-type code (e.g. "OVER").
   "TR No" only appears in Cadency_Export_Guide.xlsx's idealized sample
   sheet, never in a real export. Both business docs (the Business
   Requirements doc and the Monthly SAP Trial Balance Procedure doc) also
   consistently label this "Cadency Transaction Type - Ref 9". Reference 9
   is therefore treated as the expected column; "TR No" is kept as a
   fallback only in case an idealized-format file is ever loaded, and it
   still raises if a file somehow has both (rather than silently guessing).

2. SAP EXPORT LAYOUT -- CONFIRMED (2026-09-24)
   Ryan hit this directly: a real SAP GL line-item export (the classic
   FI display-document field set -- Document Type, Posting Key, Clearing
   Document, Profit Center, Segment, Offsetting Account, etc.) uses "Text"
   and "Document Date" exactly as assumed, but the amount field is named
   "Amount in Local Currency" -- not "Local Currency Amount" as originally
   guessed (same words, different order, so it never matched and Phase 1
   silently produced $0 for every SAP row until this was caught). The
   export also has several *other* amount-like columns for parallel
   currencies (Amount in Loc.Crcy 2/3, Freely Defined Curr. Amt. 2-8) --
   those are intentionally NOT candidates here; "Amount in Local Currency"
   is the one that corresponds to the plain "Amount" the business docs
   describe.

3. CADENCY AMOUNT COLUMN -- CONFIRMED (2026-10-20)
   Sean reconciled a real day by hand and got an exact match; the tool
   didn't, by tens of millions of dollars. Root cause: Cadency's "Amount"
   column is unsigned -- always positive, for both DR and CR rows alike --
   while "TA" (True Amount, spelled out in full in the idealized
   Cadency_Export_Guide.xlsx sample) is correctly signed: negative for DR,
   positive for CR. Summing "Amount" means debits and credits add together
   instead of netting, which silently inflates the total by roughly 2x
   whatever the DR side contributed -- a large, confident-looking, totally
   wrong number instead of a clear error. "Amount" is kept as a last-resort
   fallback candidate only for the synthetic single-column sample data in
   sample_data/ and tests/, which was never built to exercise this
   distinction -- real exports should always have "TA" or "True Amount"
   and should never fall through to it.

4. TREASURY / BANK EXPORT LAYOUT -- CONFIRMED (2026-10-27)
   The real Treasury export (9.1 Treasury.xlsx, and the same blocks pasted
   into Sean's July 2026 working file) has NO header row: every row is
   Date | Bank ID | Account | Amount | Flow Code, optionally followed by
   blank / free-text note columns, and ends with a footer row holding the
   account's net total and a row count in the Flow Code position. Read
   with a header, pandas turns the first transaction into column names and
   nothing resolves. normalize_bank_export puts that row back as data,
   names the columns positionally, and drops anything whose Flow Code
   isn't a +/- code (the footer). Files that do carry a "Flow Code" header
   pass through unchanged.

   Two more shapes of the same export, both from Sean's Phase 3 test
   workbook (2026-11-18, the "Sept Reclaim bank Statements" tab):
   * A blank first row. pandas makes that the header ("Unnamed: 0" ...
     "Unnamed: 9"), so every transaction is already a data row and there's
     nothing to put back.
   * Every Flow Code numeric-looking ("+166" on every row). pandas converts
     a column like that to numbers, so "+166" arrives as 166 and "-468" as
     -468 -- the sign is lost on positive codes. flow_code_text gives it
     back. The footer's row count sits in the same position, so a bare
     number only counts as a code on a transaction row: one with a real
     date and an Account (the footer has no Account). That also keeps an
     unrelated all-number file from being read as a Treasury export.

5. DCU RECLAIMS SHEET -- FROM SEAN'S PHASE 3 TEST DATA (2026-11-18)
   DCU's notice of reclaims whose funds were split with another account.
   One row per split: Contract Number, Certificate Number, Cycle Date,
   Effective Date, Debit Account, an account column literally headed
   "Acct# 19803075 or 19803095 or 147", Trans Type, "Total Amount (absolute
   value only)" and IA Acct Notes. The account column is matched on its
   "Acct#" prefix, so a different list of example accounts in the header
   still resolves. See core.matching.run_phase3 for how the rows are used.
"""

from __future__ import annotations

import numbers
import re
from datetime import date

import pandas as pd

TRANS_TYPE_CODE_CANDIDATES = ["Reference 9", "TR No"]
CADENCY_AMOUNT_CANDIDATES = ["TA", "True Amount", "Amount"]

SAP_TEXT_COLUMN_CANDIDATES = ["Text", "SAP Text", "TEXT"]
SAP_DATE_COLUMN_CANDIDATES = ["Document Date", "Doc Date"]
SAP_AMOUNT_COLUMN_CANDIDATES = ["Amount", "Entry Amount", "Local Currency Amount", "Amount in Local Currency"]

BANK_FLOW_CODE_COLUMN_CANDIDATES = ["Flow Code", "Bank Flow Code"]
BANK_DATE_COLUMN_CANDIDATES = ["Date", "Value Date", "Post Date"]
BANK_AMOUNT_COLUMN_CANDIDATES = ["Amount", "Net Amount"]

BANK_HEADERLESS_COLUMNS = ["Date", "Bank ID", "Account", "Amount", "Flow Code"]
_FLOW_CODE_RE = re.compile(r"^[+-][A-Za-z0-9_]+$")

DCU_CERTIFICATE_COLUMN_CANDIDATES = ["Certificate Number", "Certificate", "Cert Number"]
DCU_CONTRACT_COLUMN_CANDIDATES = ["Contract Number", "Contract"]
DCU_EFFECTIVE_DATE_COLUMN_CANDIDATES = ["Effective Date"]
DCU_AMOUNT_COLUMN_CANDIDATES = ["Total Amount (absolute value only)", "Total Amount"]
DCU_ACCOUNT_COLUMN_PREFIXES = ["Acct#", "Acct #"]


def _is_flow_code(value) -> bool:
    return isinstance(value, str) and bool(_FLOW_CODE_RE.match(value.strip()))


def _is_blank(value) -> bool:
    if isinstance(value, str):
        return not value.strip()
    return value is None or bool(pd.isna(value))


def _is_date(value) -> bool:
    """A real date, or date text as a .csv hands it back."""
    if isinstance(value, date):
        return True
    return isinstance(value, str) and pd.notna(pd.to_datetime(value, errors="coerce"))


def flow_code_text(value) -> str | None:
    """A Flow Code as "+166" / "-GDSCK_I" text, or None if it isn't one.
    Numbers get their sign back (166 -> "+166") -- see module docstring,
    item 4: pandas reads an all-numeric code column as numbers.
    """
    if isinstance(value, str):
        return value.strip() if _is_flow_code(value) else None
    if isinstance(value, numbers.Real) and not isinstance(value, bool) and not pd.isna(value) and float(value).is_integer():
        return f"{int(value):+d}"
    return None


def has_blank_header(df: pd.DataFrame) -> bool:
    """True when pandas built the header from an empty first row."""
    return len(df.columns) > 0 and all(isinstance(c, str) and c.startswith("Unnamed:") for c in df.columns)


def normalize_bank_export(bank_df: pd.DataFrame) -> pd.DataFrame:
    """Return the bank export with named columns and only flow-code rows --
    see module docstring, item 4. Leaves the frame alone if it already has
    a recognised Flow Code header, or doesn't look like the headerless
    layout either (so resolve_bank_columns still raises its normal error).
    """
    if any(c in bank_df.columns for c in BANK_FLOW_CODE_COLUMN_CANDIDATES):
        return bank_df
    n = len(BANK_HEADERLESS_COLUMNS)
    if len(bank_df.columns) < n:
        return bank_df

    if has_blank_header(bank_df):
        df = bank_df.copy()
    elif _is_flow_code(bank_df.columns[n - 1]):
        first_row = [None if str(c).startswith("Unnamed:") else c for c in bank_df.columns]
        df = pd.concat([pd.DataFrame([first_row], columns=bank_df.columns), bank_df], ignore_index=True)
    else:
        return bank_df

    df.columns = BANK_HEADERLESS_COLUMNS + [f"Column {i + 1}" for i in range(n, len(df.columns))]
    df["Flow Code"] = [
        flow_code_text(code) if isinstance(code, str) or (_is_date(day) and not _is_blank(account)) else None
        for code, account, day in zip(df["Flow Code"], df["Account"], df["Date"])
    ]
    df = df[df["Flow Code"].notna()].reset_index(drop=True)
    if df.empty:
        return bank_df
    df["Amount"] = pd.to_numeric(df["Amount"])
    df["Account"] = normalize_code(df["Account"]).str.lstrip("0")
    return df


def normalize_code(series: pd.Series) -> pd.Series:
    """Trans-type / Reference 7 codes as clean strings. Excel hands numeric
    codes back as int or float depending on how the cell was saved, so the
    same 5801 can arrive as "5801" or "5801.0" -- either has to match.
    """
    return series.fillna("").astype(str).str.strip().str.removesuffix(".0")


def _resolve_column(df: pd.DataFrame, candidates: list[str], what: str) -> str:
    present = [c for c in candidates if c in df.columns]
    if not present:
        raise ValueError(
            f"Could not find the {what} column in this file. "
            f"Looked for: {candidates}. Columns present: {list(df.columns)}"
        )
    if len(present) > 1:
        raise ValueError(
            f"Found more than one candidate column for {what} ({present}) in "
            "this file -- need a human to confirm which one is authoritative "
            "before this can run safely."
        )
    return present[0]


def resolve_trans_type_column(cadency_df: pd.DataFrame) -> str:
    """Return whichever candidate column holds the Cadency trans-type code
    (Reference 9, or "TR No" as a fallback) -- see module docstring, item 1.
    """
    return _resolve_column(cadency_df, TRANS_TYPE_CODE_CANDIDATES, "Cadency trans-type code")


def resolve_cadency_amount_column(cadency_df: pd.DataFrame) -> str:
    """Return whichever candidate column holds the correctly-signed Cadency
    amount, preferring the first match in CADENCY_AMOUNT_CANDIDATES order
    (TA > True Amount > Amount) -- see module docstring, item 3.

    Unlike _resolve_column, this does NOT treat multiple candidates being
    present as an ambiguity error: real Cadency exports legitimately have
    both "TA" (signed) and "Amount" (unsigned) as distinct columns side by
    side, so the correct behavior is to prefer the signed one, not flag the
    file as ambiguous.
    """
    for candidate in CADENCY_AMOUNT_CANDIDATES:
        if candidate in cadency_df.columns:
            return candidate
    raise ValueError(
        "Could not find a Cadency amount column in this file. "
        f"Looked for (in priority order): {CADENCY_AMOUNT_CANDIDATES}. "
        f"Columns present: {list(cadency_df.columns)}"
    )


def resolve_sap_columns(sap_df: pd.DataFrame) -> dict:
    """Return {'text': ..., 'date': ..., 'amount': ...} column names for the
    SAP export -- see module docstring, item 2.
    """
    return {
        "text": _resolve_column(sap_df, SAP_TEXT_COLUMN_CANDIDATES, "SAP Text"),
        "date": _resolve_column(sap_df, SAP_DATE_COLUMN_CANDIDATES, "SAP Document Date"),
        "amount": _resolve_column(sap_df, SAP_AMOUNT_COLUMN_CANDIDATES, "SAP Amount"),
    }


def resolve_bank_columns(bank_df: pd.DataFrame) -> dict:
    """Return {'flow_code': ..., 'date': ..., 'amount': ...} column names for
    the Treasury/bank statement export. The real export is headerless --
    run it through normalize_bank_export first (module docstring, item 4).
    """
    return {
        "flow_code": _resolve_column(bank_df, BANK_FLOW_CODE_COLUMN_CANDIDATES, "Bank Flow Code"),
        "date": _resolve_column(bank_df, BANK_DATE_COLUMN_CANDIDATES, "Bank Date"),
        "amount": _resolve_column(bank_df, BANK_AMOUNT_COLUMN_CANDIDATES, "Bank Amount"),
    }


def _resolve_optional_column(df: pd.DataFrame, candidates: list[str], what: str) -> str | None:
    """Like _resolve_column, but None when the file simply doesn't have it."""
    if not any(c in df.columns for c in candidates):
        return None
    return _resolve_column(df, candidates, what)


def _resolve_prefixed_column(df: pd.DataFrame, prefixes: list[str], what: str) -> str:
    present = [c for c in df.columns if isinstance(c, str) and c.strip().startswith(tuple(prefixes))]
    if not present:
        raise ValueError(
            f"Could not find the {what} column in this file. "
            f"Looked for a header starting with: {prefixes}. Columns present: {list(df.columns)}"
        )
    if len(present) > 1:
        raise ValueError(
            f"Found more than one candidate column for {what} ({present}) in "
            "this file -- need a human to confirm which one is authoritative "
            "before this can run safely."
        )
    return present[0]


def resolve_dcu_columns(dcu_df: pd.DataFrame) -> dict:
    """Return the DCU reclaims sheet's column names -- see module docstring,
    item 5. 'contract' and 'effective_date' are None when absent: they only
    confirm / disambiguate a match, the certificate alone can make one.
    """
    return {
        "certificate": _resolve_column(dcu_df, DCU_CERTIFICATE_COLUMN_CANDIDATES, "DCU Certificate Number"),
        "contract": _resolve_optional_column(dcu_df, DCU_CONTRACT_COLUMN_CANDIDATES, "DCU Contract Number"),
        "effective_date": _resolve_optional_column(dcu_df, DCU_EFFECTIVE_DATE_COLUMN_CANDIDATES, "DCU Effective Date"),
        "account": _resolve_prefixed_column(dcu_df, DCU_ACCOUNT_COLUMN_PREFIXES, "DCU account (Acct#)"),
        "amount": _resolve_column(dcu_df, DCU_AMOUNT_COLUMN_CANDIDATES, "DCU Total Amount"),
    }
