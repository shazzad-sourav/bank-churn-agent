"""Run the evaluation set against the live agent and write a report.

    python -m eval.run_eval                 # uses MODEL from .env (Gemini by default)
    python -m eval.run_eval --resume        # continue a stopped run; re-runs only failed/missing ones
    python -m eval.run_eval --model openai:gpt-4o-mini
    python -m eval.run_eval --only q03 q12  # a few questions

Each question runs in a fresh conversation. Approval requests are auto-REJECTED, so the
eval never writes files. Progress is saved after every question, and the run stops early
if the free-tier quota is used up on every model, so nothing is lost. Results go to
eval/results/ as Markdown and JSON.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from churn_agent import config  # noqa: E402
from churn_agent.agent import ChurnAnalyst, is_daily_quota  # noqa: E402
from churn_agent.tools import execute_sql  # noqa: E402
from eval.scoring import score_item  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
QUOTA_MARKERS = ("resource_exhausted", "429", "quota")


def row_count() -> int:
    return execute_sql("SELECT COUNT(*) FROM customers")["rows"][0][0]


def looks_like_quota(text: str) -> bool:
    t = (text or "").lower()
    return is_daily_quota(t) or any(s in t for s in QUOTA_MARKERS)


def run_one(item: dict, model: str) -> dict:
    before = row_count()
    agent = ChurnAnalyst(model=model)
    start = time.perf_counter()
    error, turn, paused = "", None, False
    try:
        turn = agent.ask(item["question"])
        paused = turn.pending_approval is not None
        if paused:  # never actually export during the eval
            after_reject = agent.decide(False, "Evaluation run: export declined.")
            turn.tool_calls += after_reject.tool_calls
            turn.models += [m for m in after_reject.models if m not in turn.models]
            turn.answer = turn.answer or after_reject.answer
    except Exception as exc:  # noqa: BLE001 - record and keep going
        error = f"{type(exc).__name__}: {str(exc)[:300]}"
    seconds = time.perf_counter() - start
    after = row_count()
    if turn is None:
        passed, why, answer, calls, models = False, f"ERROR {error}", "", [], []
    else:
        passed, why = score_item(item, turn.answer, turn.tool_calls, paused, before, after)
        answer, calls, models = turn.answer, turn.tool_calls, turn.models
    return {
        "id": item["id"], "type": item["type"], "question": item["question"],
        "passed": passed, "reason": why, "seconds": round(seconds, 1),
        "tool_calls": [c["name"] for c in calls], "models": models, "answer": answer,
        "quota_error": bool(error) and looks_like_quota(error),
    }


def write_report(model: str, items: list[dict], results: dict[str, dict]) -> Path:
    rows = [results[i["id"]] for i in items if i["id"] in results]
    passed = sum(r["passed"] for r in rows)
    total = len(items)
    by_type: dict[str, list[int]] = {}
    for i in items:
        by_type.setdefault(i["type"], [0, 0])
        by_type[i["type"]][1] += 1
    for r in rows:
        by_type[r["type"]][0] += r["passed"]
    avg_s = sum(r["seconds"] for r in rows) / max(len(rows), 1)
    avg_tools = sum(len(r["tool_calls"]) for r in rows) / max(len(rows), 1)
    used = sorted({m for r in rows for m in r.get("models", [])})
    missing = total - len(rows)

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    slug = model.replace(":", "_").replace("/", "_")
    (OUT / f"{stamp}_{slug}.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    lines = [
        f"# Eval results: `{model}`",
        "",
        f"Run {datetime.now():%Y-%m-%d %H:%M}. **{passed}/{total} passed ({passed / total:.0%})**. "
        f"Average {avg_s:.1f}s and {avg_tools:.1f} tool calls per question."
        + (f" {missing} not run yet." if missing else ""),
        "",
        f"Models that answered: {', '.join(f'`{m}`' for m in used) or 'n/a'}",
        "",
        "| Category | Passed |",
        "|---|---|",
        *[f"| {k} | {v[0]}/{v[1]} |" for k, v in by_type.items()],
        "",
        "| Id | Result | Question | Tools used | Note |",
        "|---|---|---|---|---|",
        *[f"| {r['id']} | {'✅' if r['passed'] else '❌'} | {r['question']} | "
          f"{', '.join(r['tool_calls']) or '-'} | {r['reason']} |" for r in rows],
    ]
    report = OUT / f"{stamp}_{slug}.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "latest.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=config.MODEL)
    parser.add_argument("--only", nargs="*", help="question ids to run")
    parser.add_argument("--resume", action="store_true",
                        help="keep earlier passes and re-run only failed or missing questions")
    parser.add_argument("--pause", type=float, default=6.0,
                        help="seconds between questions (free tiers have per-minute limits)")
    args = parser.parse_args()

    items = yaml.safe_load((HERE / "questions.yaml").read_text(encoding="utf-8"))
    OUT.mkdir(exist_ok=True)
    slug = args.model.replace(":", "_").replace("/", "_")
    progress_file = OUT / f"progress_{slug}.json"

    results: dict[str, dict] = {}
    if args.resume and progress_file.exists():
        results = {r["id"]: r for r in json.loads(progress_file.read_text(encoding="utf-8"))}
    todo = [i for i in items if not (i["id"] in results and results[i["id"]]["passed"])]
    if args.only:
        todo = [i for i in todo if i["id"] in set(args.only)]
    if args.resume:
        print(f"Resuming: {len(items) - len(todo)} already passed, {len(todo)} to run.")

    quota_streak = 0
    for n, item in enumerate(todo, 1):
        r = run_one(item, args.model)
        results[item["id"]] = r
        progress_file.write_text(json.dumps(list(results.values()), indent=2), encoding="utf-8")
        mark = "PASS" if r["passed"] else "FAIL"
        model_note = f", {'/'.join(r['models'])}" if r["models"] else ""
        print(f"[{n:>2}/{len(todo)}] {mark} {item['id']} ({r['seconds']}s, "
              f"{len(r['tool_calls'])} tools{model_note}) {r['reason'][:160]}")
        quota_streak = quota_streak + 1 if r["quota_error"] else 0
        if quota_streak >= 2:
            print("\nStopped: the free-tier quota is used up on every model. Daily quotas reset at "
                  "midnight Pacific (3 a.m. Toronto). Progress is saved; continue later with:\n"
                  "    python -m eval.run_eval --resume --pause 12")
            break
        if n < len(todo):
            time.sleep(args.pause)

    report = write_report(args.model, items, results)
    passed = sum(r["passed"] for r in results.values())
    print(f"\n{passed}/{len(items)} passed. Report: {report}")
    return 0 if passed == len(items) else 1


if __name__ == "__main__":
    raise SystemExit(main())
