"""Every expected answer in the eval set is checked against the database."""
from pathlib import Path

import pytest
import yaml

from churn_agent.tools import execute_sql

ITEMS = yaml.safe_load((Path(__file__).resolve().parent.parent / "eval" / "questions.yaml").read_text(encoding="utf-8"))
NUMERIC = [i for i in ITEMS if i["type"] == "numeric"]


@pytest.mark.parametrize("item", NUMERIC, ids=[i["id"] for i in NUMERIC])
def test_expected_values_match_data(item):
    row = execute_sql(item["truth_sql"])["rows"][0]
    assert len(row) == len(item["expect"])
    for got, want in zip(row, item["expect"]):
        assert abs(float(got) - want) <= max(item.get("tol", 0.5), abs(want) * item.get("rel_tol", 0)), item["id"]


def test_headline_numbers_match_power_bi_project():
    r = execute_sql("SELECT COUNT(*), SUM(churned), SUM(CASE WHEN churned=0 AND risk_tier='High' THEN 1 END) FROM customers")["rows"][0]
    assert r == [10127, 1627, 1137]
