"""End-to-end agent loop with a scripted model: no API key or network needed."""
from langchain_core.messages import AIMessage

from churn_agent.agent import ChurnAnalyst
from fake_model import ScriptedToolModel


def call(name, args, i):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": f"call_{i}"}])


def test_question_uses_sql_and_answers():
    model = ScriptedToolModel(responses=[
        call("get_schema", {}, 1),
        call("run_sql", {"query": "SELECT ROUND(AVG(churned)*100,1) FROM customers"}, 2),
        AIMessage(content="The overall churn rate is 16.1%."),
    ])
    turn = ChurnAnalyst(model=model).ask("What is the churn rate?")
    assert turn.answer == "The overall churn rate is 16.1%."
    assert [c["name"] for c in turn.tool_calls] == ["get_schema", "run_sql"]
    assert "16.1" in turn.tool_calls[1]["output"]


def test_docs_search_tool_runs():
    model = ScriptedToolModel(responses=[
        call("search_docs", {"question": "warning signs in the risk score"}, 1),
        AIMessage(content="Six warning signs."),
    ])
    turn = ChurnAnalyst(model=model).ask("How does the score work?")
    assert "risk_score_method.md" in turn.tool_calls[0]["output"]


def test_export_pauses_for_approval_and_reject_writes_nothing(tmp_path, monkeypatch):
    from churn_agent import config
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path)
    model = ScriptedToolModel(responses=[
        call("export_watchlist", {"limit": 5}, 1),
        AIMessage(content="Okay, I won't export it."),
    ])
    agent = ChurnAnalyst(model=model)
    turn = agent.ask("Export a call list")
    assert turn.pending_approval is not None
    assert turn.pending_approval["action_requests"][0]["name"] == "export_watchlist"
    turn = agent.decide(False)
    assert list(tmp_path.iterdir()) == []


def test_export_after_approval_writes_csv(tmp_path, monkeypatch):
    from churn_agent import config
    monkeypatch.setattr(config, "EXPORT_DIR", tmp_path)
    model = ScriptedToolModel(responses=[
        call("export_watchlist", {"limit": 5}, 1),
        AIMessage(content="Exported 5 customers."),
    ])
    turn = ChurnAnalyst(model=model).ask_with_approval("Export a call list", lambda req: True)
    files = list(tmp_path.glob("watchlist_*.csv"))
    assert len(files) == 1
    assert len(files[0].read_text().splitlines()) == 6  # header + 5
    assert any(c["name"] == "export_watchlist" for c in turn.tool_calls)
