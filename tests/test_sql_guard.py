import pytest

from churn_agent.sql_guard import UnsafeSQLError, validate_sql
from churn_agent.tools import execute_sql, run_sql


@pytest.mark.parametrize("sql", [
    "SELECT COUNT(*) FROM customers",
    "with t as (select churned from customers) select avg(churned) from t",
    "SELECT * FROM customers LIMIT 5; ",
    "-- comment\nSELECT 1",
])
def test_allows_reads(sql):
    assert validate_sql(sql)


@pytest.mark.parametrize("sql", [
    "DELETE FROM customers",
    "UPDATE customers SET credit_limit = 0",
    "DROP TABLE customers",
    "SELECT 1; DROP TABLE customers",
    "INSERT INTO customers (client_id) VALUES ('x')",
    "PRAGMA table_info(customers)",
    "ATTACH DATABASE 'x.db' AS x",
    "",
])
def test_blocks_writes(sql):
    with pytest.raises(UnsafeSQLError):
        validate_sql(sql)


def test_tool_reports_block_and_db_is_untouched():
    before = execute_sql("SELECT COUNT(*) FROM customers")["rows"][0][0]
    out = run_sql.invoke({"query": "DELETE FROM customers"})
    assert out.startswith("BLOCKED")
    assert execute_sql("SELECT COUNT(*) FROM customers")["rows"][0][0] == before == 10127


def test_connection_is_read_only_even_if_text_check_is_bypassed():
    from churn_agent.database import read_only_connection
    con = read_only_connection()
    with pytest.raises(Exception):
        con.execute("DELETE FROM customers")
    con.close()


def test_row_cap():
    res = execute_sql("SELECT client_id FROM customers")
    assert res["row_count"] == 50 and res["truncated"] is True


def test_sql_error_is_returned_to_model():
    assert run_sql.invoke({"query": "SELECT no_such_column FROM customers"}).startswith("SQL ERROR")
