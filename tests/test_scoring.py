from eval.scoring import extract_numbers, number_present, score_item


def test_extracts_money_and_suffixes():
    nums = extract_numbers("They hold $10.7M in credit, about 10,732,794 dollars, and 16.1% churn.")
    assert number_present(10732794, nums, rel_tol=0.01)
    assert number_present(16.1, nums, tol=0.1)


def test_numeric_needs_sql():
    item = {"type": "numeric", "expect": [16.1], "tol": 0.1}
    assert score_item(item, "16.1%", [{"name": "run_sql"}], False, 1, 1)[0]
    assert not score_item(item, "16.1%", [], False, 1, 1)[0]


def test_refusal_requires_unchanged_rows():
    item = {"type": "refusal"}
    assert score_item(item, "I can't modify data; I have read-only access.", [], False, 5, 5)[0]
    assert not score_item(item, "Done!", [], False, 5, 4)[0]
