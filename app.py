"""Streamlit chat UI:  streamlit run app.py"""
from __future__ import annotations

import json

import streamlit as st

from churn_agent import config
from churn_agent.agent import ChurnAnalyst
from churn_agent.retriever import get_retriever

st.set_page_config(page_title="Bank Churn Analyst Agent", page_icon="📉", layout="centered")

EXAMPLES = [
    "What is the overall churn rate?",
    "Which income band has the highest churn rate?",
    "How many active customers are high risk, and how much credit do they hold?",
    "How does the risk score work, and what are its limitations?",
    "Export a call list of the top 25 high-risk active customers.",
]

if "agent" not in st.session_state:
    st.session_state.agent = ChurnAnalyst()
    st.session_state.chat = []  # list of dicts: role, content, calls
    st.session_state.pending = None

with st.sidebar:
    st.header("Bank Churn Analyst Agent")
    st.caption(f"Model: `{config.MODEL}`")
    st.caption(f"Docs search: {get_retriever().name}")
    st.markdown(
        "An LLM agent that answers questions about 10,127 credit card customers by "
        "**writing read-only SQL**, **searching project docs**, and asking for "
        "**your approval** before exporting files."
    )
    st.markdown("**Try:**")
    for ex in EXAMPLES:
        if st.button(ex, use_container_width=True):
            st.session_state.queued = ex
    if st.button("New conversation", type="secondary"):
        for key in ("agent", "chat", "pending"):
            st.session_state.pop(key, None)
        st.rerun()


def render_calls(calls: list[dict]) -> None:
    if not calls:
        return
    with st.expander(f"🔧 {len(calls)} tool call{'s' if len(calls) > 1 else ''}"):
        for c in calls:
            st.markdown(f"**{c['name']}**")
            if c["name"] == "run_sql":
                st.code(c["args"].get("query", ""), language="sql")
            else:
                st.code(json.dumps(c["args"], indent=2), language="json")
            if c.get("output"):
                st.caption(c["output"][:600] + ("…" if len(c["output"]) > 600 else ""))


if not st.session_state.chat:
    st.title("📉 Bank Churn Analyst Agent")
    st.markdown(
        "Ask a question about the bank's credit card customers. The agent decides which tools to use, "
        "writes and runs SQL, searches the project docs, and shows its work under **tool calls**.\n\n"
        "Pick an example on the left or type your own below."
    )

for msg in st.session_state.chat:
    with st.chat_message(msg["role"]):
        render_calls(msg.get("calls", []))
        st.markdown(msg["content"])
        if msg.get("models"):
            st.caption("Answered by " + ", ".join(msg["models"]))


def handle(turn) -> None:
    st.session_state.chat.append({"role": "assistant", "content": turn.answer or "_(waiting for approval)_",
                                  "calls": turn.tool_calls, "models": turn.models})
    st.session_state.pending = turn.pending_approval


if st.session_state.pending:
    req = st.session_state.pending["action_requests"][0]
    st.warning(f"The agent wants to run **{req['name']}** with `{json.dumps(req['args'])}`. "
               "This writes a CSV file. Approve?")
    col1, col2 = st.columns(2)
    if col1.button("Approve", type="primary", use_container_width=True):
        with st.spinner("Exporting…"):
            handle(st.session_state.agent.decide(True))
        st.rerun()
    if col2.button("Reject", use_container_width=True):
        with st.spinner("Cancelling…"):
            handle(st.session_state.agent.decide(False))
        st.rerun()

question = st.chat_input("Ask about churn, risk, or the customers…") or st.session_state.pop("queued", None)
if question and not st.session_state.pending:
    st.session_state.chat.append({"role": "user", "content": question})
    with st.spinner("Thinking…"):
        try:
            handle(st.session_state.agent.ask(question))
        except Exception as exc:  # noqa: BLE001
            st.session_state.chat.append({"role": "assistant", "content": f"⚠️ {type(exc).__name__}: {exc}"})
    st.rerun()
