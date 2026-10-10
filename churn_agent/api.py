"""Minimal REST API:  uvicorn churn_agent.api:app --reload

POST /ask      {"question": "...", "thread_id": "optional"}  -> answer, tool calls, approval request
POST /decide   {"thread_id": "...", "approve": true}         -> resumes a paused export
GET  /health
"""
from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from . import config
from .agent import ChurnAnalyst

app = FastAPI(title="Bank Churn Analyst Agent", version="1.0")
_sessions: dict[str, ChurnAnalyst] = {}


class AskIn(BaseModel):
    question: str
    thread_id: str | None = None


class DecideIn(BaseModel):
    thread_id: str
    approve: bool
    reason: str = ""


def _out(thread_id: str, turn) -> dict:
    return {"thread_id": thread_id, "answer": turn.answer, "tool_calls": turn.tool_calls,
            "pending_approval": turn.pending_approval}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": config.MODEL}


@app.post("/ask")
def ask(body: AskIn) -> dict:
    thread_id = body.thread_id or str(uuid.uuid4())
    agent = _sessions.setdefault(thread_id, ChurnAnalyst(thread_id=thread_id))
    return _out(thread_id, agent.ask(body.question))


@app.post("/decide")
def decide(body: DecideIn) -> dict:
    agent = _sessions.get(body.thread_id)
    if agent is None:
        raise HTTPException(404, "Unknown thread_id")
    return _out(body.thread_id, agent.decide(body.approve, body.reason))
