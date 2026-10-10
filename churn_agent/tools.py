"""Tools the agent can call.

- get_schema:      table and column descriptions, so the model writes correct SQL
- run_sql:         read-only SQL against the customers table (guardrailed)
- search_docs:     retrieval over the project docs (method, findings, data dictionary)
- export_watchlist: writes a CSV of high-risk active customers. This is the only tool
                   with a side effect, so the agent pauses for human approval first
                   (see HumanInTheLoopMiddleware in agent.py).
"""
from __future__ import annotations

import csv
import json
from datetime import datetime

from langchain_core.tools import tool

from . import config
from .database import COLUMN_NOTES, TABLE, read_only_connection
from .retriever import get_retriever
from .sql_guard import UnsafeSQLError, read_only_authorizer, validate_sql


def execute_sql(query: str, max_rows: int = config.MAX_SQL_ROWS) -> dict:
    """Run a guarded, read-only query. Returns a dict (also used by tests and the eval)."""
    cleaned = validate_sql(query)
    con = read_only_connection()
    con.set_authorizer(read_only_authorizer)
    try:
        cur = con.execute(cleaned)
        columns = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(max_rows + 1)
    finally:
        con.close()
    truncated = len(rows) > max_rows
    return {
        "columns": columns,
        "rows": [list(r) for r in rows[:max_rows]],
        "row_count": min(len(rows), max_rows),
        "truncated": truncated,
    }


@tool
def get_schema() -> str:
    """Describe the `customers` table: one row per credit card customer, with every column explained.
    Call this before writing SQL if you are unsure of a column name or its values."""
    con = read_only_connection()
    try:
        cols = [(r[1], r[2]) for r in con.execute(f"PRAGMA table_info({TABLE})")]
        n = con.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
    finally:
        con.close()
    lines = [f"Table `{TABLE}` ({n:,} rows). SQLite dialect.", "Columns:"]
    lines += [f"- {name} ({typ}): {COLUMN_NOTES.get(name, '')}" for name, typ in cols]
    lines.append("Churn rate = AVG(churned) or SUM(churned) * 1.0 / COUNT(*).")
    return "\n".join(lines)


@tool
def run_sql(query: str) -> str:
    """Run ONE read-only SQLite SELECT query on the `customers` table and return the rows as JSON.
    Use it for every number you report: counts, churn rates, averages, top-N lists.
    Only SELECT/WITH queries are allowed; anything that writes is blocked.
    Results are capped at 50 rows, so aggregate or use LIMIT."""
    try:
        result = execute_sql(query)
    except UnsafeSQLError as exc:
        return f"BLOCKED: {exc}"
    except Exception as exc:  # noqa: BLE001 - return SQL errors to the model so it can fix the query
        return f"SQL ERROR: {exc}. Check column names with get_schema."
    return json.dumps(result, default=str)


@tool
def search_docs(question: str) -> str:
    """Search the project documentation: the risk score method and its limitations, key findings and
    recommendations, and the data dictionary. Use it for 'how', 'why', definitions and recommendations.
    Returns the most relevant passages with their source file."""
    hits = get_retriever().search(question, k=3)
    if not hits:
        return "No relevant passages found."
    return "\n\n".join(f"[{c.source} > {c.heading}]\n{c.text}" for c, _ in hits)


@tool
def export_watchlist(limit: int = 100, min_risk_score: int = 3) -> str:
    """Export a CSV call list of ACTIVE customers with risk_score >= min_risk_score, highest risk first.
    This writes a file, so a human must approve it before it runs. Only use it when the user asks
    for a list, file or export."""
    limit = max(1, min(int(limit), 5000))
    query = (
        "SELECT client_id, customer_age, income_category, card_category, total_trans_ct, "
        "months_inactive_12_mon, contacts_count_12_mon, total_relationship_count, credit_limit, "
        f"risk_score FROM {TABLE} WHERE churned = 0 AND risk_score >= {int(min_risk_score)} "
        "ORDER BY risk_score DESC, total_trans_ct ASC"
    )
    result = execute_sql(query, max_rows=limit)
    config.EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = config.EXPORT_DIR / f"watchlist_{datetime.now():%Y%m%d_%H%M%S}.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(result["columns"])
        writer.writerows(result["rows"])
    return f"Exported {result['row_count']} customers to {path}"


ALL_TOOLS = [get_schema, run_sql, search_docs, export_watchlist]
