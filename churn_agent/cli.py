"""Chat with the agent in the terminal:  python -m churn_agent.cli"""
from __future__ import annotations

import json

from . import config
from .agent import ChurnAnalyst

EXAMPLES = [
    "What is the overall churn rate?",
    "Which income band churns the most?",
    "How does the risk score work?",
    "Export a call list of the top 25 high-risk active customers.",
]


def show_calls(calls: list[dict]) -> None:
    for c in calls:
        args = json.dumps(c["args"], ensure_ascii=False)
        print(f"  ↳ {c['name']}({args[:160]}{'…' if len(args) > 160 else ''})")


def main() -> None:
    print(f"Bank Churn Analyst Agent  [model: {config.MODEL}]")
    print("Ask about the 10,127 credit card customers. Type 'exit' to quit.")
    print("Try: " + " | ".join(EXAMPLES) + "\n")
    agent = ChurnAnalyst()
    while True:
        try:
            q = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if q.lower() in {"exit", "quit", "q"}:
            break
        if not q:
            continue
        turn = agent.ask(q)
        show_calls(turn.tool_calls)
        while turn.pending_approval:
            req = turn.pending_approval["action_requests"][0]
            print(f"\n⚠ Approval needed: {req['name']}({json.dumps(req['args'])})")
            ok = input("  Approve? [y/N] ").strip().lower() == "y"
            turn = agent.decide(ok)
            show_calls(turn.tool_calls)
        print(f"\nagent › {turn.answer}\n")


if __name__ == "__main__":
    main()
