"""Pure logic for the sales/Test Drive browser: turning raw
kng-license-issuance DynamoDB items into plain dicts, and filtering them
by date range, email pattern, and product. No AWS or Tkinter calls here
-- see app.py for both of those. Kept separate so this half can be unit
tested the normal way.
"""
from __future__ import annotations

from datetime import date, datetime

DEFAULT_TABLE = "kng-license-issuance"
DEFAULT_REGION = "us-east-1"

PRODUCT_LABELS = {"server": "Server", "midi-player": "MIDI Player"}


def simplify_item(item: dict) -> dict:
    """Converts one raw DynamoDB item (the {"S": ...}/{"SS": [...]}
    attribute-value shape) into a plain dict with the fields the browser
    cares about. Missing attributes come back as None/[] rather than
    raising -- rows written before a field existed (e.g. purchases made
    before created_at was added) must still display.
    """
    return {
        "reference": item.get("reference", {}).get("S", ""),
        "source": item.get("source", {}).get("S", ""),
        "email": item.get("email", {}).get("S", ""),
        "kinds": sorted(item.get("kinds", {}).get("SS", [])),
        "short_key": item.get("short_key", {}).get("S"),
        "created_at": item.get("created_at", {}).get("S"),
        "valid_to": item.get("valid_to", {}).get("S"),
    }


def parse_date_bound(text: str) -> date | None:
    """Parses a user-typed YYYY-MM-DD filter bound. Returns None for an
    empty/blank field (no bound); raises ValueError for anything else
    unparseable, so the caller can show it as a filter error rather than
    silently ignoring a typo.
    """
    text = (text or "").strip()
    if not text:
        return None
    return datetime.strptime(text, "%Y-%m-%d").date()


def _row_date(row: dict, date_field: str) -> date | None:
    value = row.get(date_field)
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _in_date_range(row: dict, date_field: str, date_from: date | None, date_to: date | None) -> bool:
    if date_from is None and date_to is None:
        return True
    row_date = _row_date(row, date_field)
    if row_date is None:
        return False
    if date_from is not None and row_date < date_from:
        return False
    if date_to is not None and row_date > date_to:
        return False
    return True


def _matches_email_pattern(row: dict, email_pattern: str) -> bool:
    pattern = (email_pattern or "").strip().lower()
    return not pattern or pattern in row.get("email", "").lower()


def matches_filters(
    row: dict,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    email_pattern: str = "",
    product: str = "all",
) -> bool:
    if not _in_date_range(row, "created_at", date_from, date_to):
        return False
    if not _matches_email_pattern(row, email_pattern):
        return False
    if product != "all" and product not in row.get("kinds", []):
        return False
    return True


def filter_rows(
    rows: list[dict],
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    email_pattern: str = "",
    product: str = "all",
) -> list[dict]:
    """Filters, then sorts most-recent-first -- rows with no created_at
    (purchases made before that field existed) sort last, not first,
    since "" is not a valid ISO date to sort against directly.
    """
    matched = [
        row
        for row in rows
        if matches_filters(
            row, date_from=date_from, date_to=date_to, email_pattern=email_pattern, product=product
        )
    ]
    return sorted(matched, key=lambda row: row.get("created_at") or "", reverse=True)


def product_label(kind: str) -> str:
    return PRODUCT_LABELS.get(kind, kind)


DEFAULT_BETA_TESTERS_TABLE = "kng-beta-testers"


def simplify_beta_tester_item(item: dict) -> dict:
    return {
        "email": item.get("email", {}).get("S", ""),
        "added_at": item.get("added_at", {}).get("S"),
    }


def normalize_email(email: str) -> str:
    """Same normalization trial_request.handler applies before its own
    allowlist lookup -- added here case-sensitively would just mean a
    tester never matches what the Lambda actually checks."""
    return (email or "").strip().lower()


def matches_beta_tester_filters(
    row: dict, *, date_from: date | None = None, date_to: date | None = None, email_pattern: str = ""
) -> bool:
    if not _in_date_range(row, "added_at", date_from, date_to):
        return False
    return _matches_email_pattern(row, email_pattern)


def filter_beta_testers(
    rows: list[dict], *, date_from: date | None = None, date_to: date | None = None, email_pattern: str = ""
) -> list[dict]:
    matched = [
        row
        for row in rows
        if matches_beta_tester_filters(row, date_from=date_from, date_to=date_to, email_pattern=email_pattern)
    ]
    return sorted(matched, key=lambda row: row.get("added_at") or "", reverse=True)
