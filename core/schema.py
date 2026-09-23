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

2. SAP EXPORT LAYOUT
   No sample SAP export file has been provided -- only a description (a
   "Text" field and a "Document Date") from the business requirements and
   procedure docs. The column names below are a working assumption and
   should be confirmed against a real SAP export before Phase 1 results are
   trusted in production.
"""

from __future__ import annotations

import pandas as pd

TRANS_TYPE_CODE_CANDIDATES = ["Reference 9", "TR No"]

SAP_TEXT_COLUMN_CANDIDATES = ["Text", "SAP Text", "TEXT"]
SAP_DATE_COLUMN_CANDIDATES = ["Document Date", "Doc Date"]
SAP_AMOUNT_COLUMN_CANDIDATES = ["Amount", "Entry Amount", "Local Currency Amount"]

BANK_FLOW_CODE_COLUMN_CANDIDATES = ["Flow Code", "Bank Flow Code"]
BANK_DATE_COLUMN_CANDIDATES = ["Date", "Value Date", "Post Date"]
BANK_AMOUNT_COLUMN_CANDIDATES = ["Amount", "Net Amount"]


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
    the Treasury/bank statement export.

    No real bank/treasury export sample has been provided -- these are a
    working assumption based on how Flow Code activity is described in the
    business docs and tracked in Sean's July 2026 working file, and should
    be confirmed against a real export before Phase 2 is trusted in
    production.
    """
    return {
        "flow_code": _resolve_column(bank_df, BANK_FLOW_CODE_COLUMN_CANDIDATES, "Bank Flow Code"),
        "date": _resolve_column(bank_df, BANK_DATE_COLUMN_CANDIDATES, "Bank Date"),
        "amount": _resolve_column(bank_df, BANK_AMOUNT_COLUMN_CANDIDATES, "Bank Amount"),
    }
