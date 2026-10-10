"""Central settings. Everything can be overridden with environment variables or a .env file."""
from __future__ import annotations

import os
from pathlib import Path

try:  # optional: load .env when python-dotenv is installed
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = Path(os.getenv("CHURN_CSV", ROOT / "data" / "BankChurners.csv"))
DB_PATH = Path(os.getenv("CHURN_DB", ROOT / "data" / "churn.db"))
DOCS_DIR = Path(os.getenv("CHURN_DOCS", ROOT / "docs"))
VECTOR_DIR = Path(os.getenv("CHURN_VECTOR_DIR", ROOT / "data" / "chroma"))
EXPORT_DIR = Path(os.getenv("CHURN_EXPORT_DIR", ROOT / "exports"))

# "provider:model" string understood by langchain.chat_models.init_chat_model.
# Gemini free tier by default; switch with one line in .env, e.g.
#   MODEL=openai:gpt-4o-mini
#   MODEL=anthropic:claude-haiku-4-5
MODEL = os.getenv("MODEL", "google_genai:gemini-3-flash-preview")
# Tried in order if MODEL errors (daily free quota used up, or a model name Google has retired).
# Each Gemini model has its own free-tier quota, so fallbacks also stretch the free limits.
FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv(
        "FALLBACK_MODELS",
        "google_genai:gemini-3.5-flash,google_genai:gemini-3.1-flash-lite,google_genai:gemini-flash-latest",
    ).split(",")
    if m.strip()
]
TEMPERATURE = float(os.getenv("TEMPERATURE", "0"))

# Guardrails
MAX_SQL_ROWS = int(os.getenv("MAX_SQL_ROWS", "50"))  # rows returned to the model per query
MAX_MODEL_CALLS = int(os.getenv("MAX_MODEL_CALLS", "12"))  # per question, stops runaway loops
MAX_TOOL_CALLS = int(os.getenv("MAX_TOOL_CALLS", "10"))
