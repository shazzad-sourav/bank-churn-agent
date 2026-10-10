"""Show which Gemini models your API key can use:  python -m churn_agent.list_models

Google renames and retires models regularly. If the agent reports a model error, pick a
"flash" model from this list and set MODEL=google_genai:<name> in your .env file.
"""
from __future__ import annotations

import os

from . import config  # noqa: F401  (loads .env)


def main() -> None:
    from google import genai

    client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])
    names = []
    for m in client.models.list():
        actions = getattr(m, "supported_actions", None) or []
        if "generateContent" in actions and "flash" in m.name:
            names.append(m.name.removeprefix("models/"))
    print("Flash models available to your key (use with MODEL=google_genai:<name>):")
    for n in sorted(names):
        print("  ", n)


if __name__ == "__main__":
    main()
