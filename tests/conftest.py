import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))
os.environ.setdefault("RETRIEVER", "keyword")  # tests never download embedding models

from churn_agent.database import build_database  # noqa: E402

build_database()
