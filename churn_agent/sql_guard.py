"""Guardrails for model-written SQL.

Three layers, so one mistake can't get through:
1. Text checks here: a single SELECT/WITH statement, no write or admin keywords.
2. A SQLite authorizer that denies anything other than reads at execution time.
3. The connection itself is opened read-only (see database.read_only_connection).
"""
from __future__ import annotations

import re
import sqlite3

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|attach|detach|pragma|vacuum|reindex|truncate)\b",
    re.IGNORECASE,
)


class UnsafeSQLError(ValueError):
    """Raised when a query is not a single read-only statement."""


def _strip_comments(sql: str) -> str:
    sql = re.sub(r"--[^\n]*", " ", sql)
    return re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)


def validate_sql(sql: str) -> str:
    """Return a cleaned query or raise UnsafeSQLError."""
    cleaned = _strip_comments(sql).strip().rstrip(";").strip()
    if not cleaned:
        raise UnsafeSQLError("Empty query.")
    if ";" in cleaned:
        raise UnsafeSQLError("Only one statement is allowed.")
    first = cleaned.split(None, 1)[0].lower()
    if first not in {"select", "with"}:
        raise UnsafeSQLError("Only SELECT queries are allowed (read-only access).")
    if FORBIDDEN.search(cleaned):
        raise UnsafeSQLError("Query contains a write or admin keyword; read-only access only.")
    return cleaned


_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),
}


def read_only_authorizer(action: int, *_args) -> int:
    return sqlite3.SQLITE_OK if action in _ALLOWED_ACTIONS else sqlite3.SQLITE_DENY
