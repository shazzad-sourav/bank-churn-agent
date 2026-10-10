"""The Bank Churn Analyst Agent: a tool-calling LLM agent built with LangChain v1 / LangGraph.

Flow for each question:
  model decides -> calls tools (schema, SQL, docs) -> reads results -> repeats -> answers
Guardrails: read-only SQL, call limits per question, retries on rate limits, and
human approval before the one tool that writes a file.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Callable

from langchain.agents import create_agent
from langchain.agents.middleware import (
    HumanInTheLoopMiddleware,
    ModelCallLimitMiddleware,
    ModelFallbackMiddleware,
    ModelRetryMiddleware,
    ToolCallLimitMiddleware,
)
from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from . import config
from .tools import ALL_TOOLS

SYSTEM_PROMPT = """You are a careful data analyst for a bank's credit card retention team.
You answer questions about 10,127 credit card customers in the SQLite table `customers`.

How to work:
- Every number you report must come from a run_sql result in this conversation. Never guess or
  compute from memory. If unsure of column names or values, call get_schema first.
- Use search_docs for definitions, how the risk score works, its limitations, findings and
  recommendations. Mention the source file when you rely on it.
- Report churn rates as percentages with one decimal place (e.g. 16.1%), and money with $ and commas.
- Keep answers short: the direct answer first, then one or two lines of context.
- Small groups (under ~100 customers) give unreliable rates; say so when it matters.
- You only have read access. If asked to change, delete or add data, say you can't.
- Only call export_watchlist when the user explicitly asks for a list, file or export.
- If the question is unrelated to this dataset, say what you can help with instead.
"""


def make_model(model: str | None = None) -> BaseChatModel:
    # The middleware below handles retries, so the provider client only retries once itself.
    return init_chat_model(model or config.MODEL, temperature=config.TEMPERATURE,
                           max_retries=1, timeout=90)


_TRANSIENT = ("429", "resource_exhausted", "rate limit", "quota", "503", "unavailable", "overloaded", "timeout")


def is_daily_quota(text: str) -> bool:
    """Gemini free tier: the per-day request quota for this model is used up (resets midnight Pacific)."""
    t = text.lower()
    return "perday" in t or "per day" in t or "requests_per_day" in t


def _is_transient(exc: Exception) -> bool:
    """Retry per-minute rate limits and outages. A used-up daily quota won't recover by waiting,
    so it goes straight to the next fallback model, as do other errors (e.g. unknown model)."""
    text = str(exc)
    if is_daily_quota(text):
        return False
    return any(s in text.lower() for s in _TRANSIENT)


def build_agent(model: BaseChatModel | str | None = None):
    llm = model if isinstance(model, BaseChatModel) else make_model(model)
    middleware = []
    if not isinstance(model, BaseChatModel):  # real providers only, not test doubles
        primary = model or config.MODEL
        provider = primary.split(":", 1)[0]
        fallbacks = [m for m in config.FALLBACK_MODELS
                     if m != primary and m.split(":", 1)[0] == provider]
        if fallbacks:
            middleware.append(ModelFallbackMiddleware(*[make_model(m) for m in fallbacks]))
    middleware += [
        # on_failure="error" re-raises after the last retry so the fallback middleware (outer)
        # can switch to the next model. Each Gemini model has its own free-tier quota.
        ModelRetryMiddleware(max_retries=2, backoff_factor=2.0, initial_delay=15.0,
                             retry_on=_is_transient, on_failure="error"),
        ModelCallLimitMiddleware(run_limit=config.MAX_MODEL_CALLS, exit_behavior="end"),
        ToolCallLimitMiddleware(run_limit=config.MAX_TOOL_CALLS, exit_behavior="continue"),
        HumanInTheLoopMiddleware(
            interrupt_on={
                "export_watchlist": {
                    "allowed_decisions": ["approve", "reject"],
                    "description": "The agent wants to write a CSV file of customers. Approve?",
                }
            }
        ),
    ]
    return create_agent(
        llm,
        tools=ALL_TOOLS,
        system_prompt=SYSTEM_PROMPT,
        middleware=middleware,
        checkpointer=InMemorySaver(),
    )


@dataclass
class Turn:
    """Result of one question: the answer plus a trace of tool calls (for the UI and the eval)."""

    answer: str
    tool_calls: list[dict] = field(default_factory=list)
    pending_approval: dict | None = None
    models: list[str] = field(default_factory=list)  # which model(s) answered (fallbacks show here)


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # some providers return content blocks
        return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)
    return str(content)


def _collect(messages, start: int) -> tuple[str, list[dict], list[str]]:
    calls, outputs, models = [], {}, []
    for m in messages[start:]:
        if isinstance(m, ToolMessage):
            outputs[m.tool_call_id] = _text(m.content)
    for m in messages[start:]:
        if isinstance(m, AIMessage):
            name = (m.response_metadata or {}).get("model_name")
            if name and name not in models:
                models.append(name)
            for tc in m.tool_calls or []:
                calls.append({"name": tc["name"], "args": tc["args"], "output": outputs.get(tc["id"], "")})
    answer = ""
    for m in reversed(messages[start:]):
        if isinstance(m, AIMessage) and _text(m.content).strip():
            answer = _text(m.content).strip()
            break
    return answer, calls, models


class ChurnAnalyst:
    """Conversation wrapper used by the CLI, the Streamlit app, the API and the eval."""

    def __init__(self, model: BaseChatModel | str | None = None, thread_id: str | None = None):
        self.agent = build_agent(model)
        self.config = {"configurable": {"thread_id": thread_id or str(uuid.uuid4())}}

    def _history_len(self) -> int:
        state = self.agent.get_state(self.config)
        return len(state.values.get("messages", [])) if state and state.values else 0

    def _finish(self, result, start: int) -> Turn:
        answer, calls, models = _collect(result["messages"], start)
        interrupts = result.get("__interrupt__") or []
        pending = interrupts[0].value if interrupts else None
        return Turn(answer=answer, tool_calls=calls, pending_approval=pending, models=models)

    def ask(self, question: str) -> Turn:
        start = self._history_len()
        result = self.agent.invoke({"messages": [{"role": "user", "content": question}]}, self.config)
        return self._finish(result, start)

    def decide(self, approve: bool, reason: str = "") -> Turn:
        """Resume after a human-approval pause."""
        start = max(self._history_len() - 1, 0)  # include the paused tool-call message
        decision = {"type": "approve"} if approve else {
            "type": "reject",
            "message": reason or "The user declined the export. Do not retry it.",
        }
        result = self.agent.invoke(Command(resume={"decisions": [decision]}), self.config)
        return self._finish(result, start)

    def ask_with_approval(self, question: str, approve_fn: Callable[[dict], bool]) -> Turn:
        """Convenience for scripts: ask, and if the agent pauses, call approve_fn(request)."""
        turn = self.ask(question)
        calls, models = list(turn.tool_calls), list(turn.models)
        while turn.pending_approval is not None:
            turn = self.decide(approve_fn(turn.pending_approval))
            calls += turn.tool_calls
            models += [m for m in turn.models if m not in models]
        turn.tool_calls, turn.models = calls, models
        return turn
