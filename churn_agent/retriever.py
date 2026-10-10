"""Document retrieval (the RAG part).

Markdown files in docs/ are split by heading into chunks and stored in a Chroma vector
database. Chroma's default embedding model (all-MiniLM-L6-v2, ONNX) runs locally, so
retrieval costs no API calls. If the embedding model can't be loaded (for example on a
machine with no internet on first run), it falls back to keyword scoring so the agent
still works.
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from . import config


@dataclass
class Chunk:
    id: str
    source: str
    heading: str
    text: str


def load_chunks(docs_dir: Path = config.DOCS_DIR) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(docs_dir.glob("*.md")):
        heading, buf, n = path.stem, [], 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("#"):
                if buf and "".join(buf).strip():
                    chunks.append(Chunk(f"{path.stem}-{n}", path.name, heading, "\n".join(buf).strip()))
                    n += 1
                heading = line.lstrip("#").strip()
                buf = []
            else:
                buf.append(line)
        if buf and "".join(buf).strip():
            chunks.append(Chunk(f"{path.stem}-{n}", path.name, heading, "\n".join(buf).strip()))
    for c in chunks:  # give each chunk its own context line for better matching
        c.text = f"{c.heading}\n{c.text}"
    return chunks


_WORD = re.compile(r"[a-z0-9$]+")


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


class KeywordRetriever:
    """Small BM25 scorer, used as a fallback and in offline tests."""

    name = "keyword (BM25)"

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        self.docs = [Counter(_tokens(c.text)) for c in chunks]
        self.avg_len = sum(sum(d.values()) for d in self.docs) / max(len(self.docs), 1)
        df = Counter(t for d in self.docs for t in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 3) -> list[tuple[Chunk, float]]:
        q = _tokens(query)
        scores = []
        for chunk, doc in zip(self.chunks, self.docs):
            length = sum(doc.values())
            s = 0.0
            for t in q:
                if t in doc:
                    tf = doc[t]
                    s += self.idf.get(t, 0) * tf * 2.2 / (tf + 1.2 * (0.25 + 0.75 * length / self.avg_len))
            scores.append((chunk, s))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [x for x in scores[:k] if x[1] > 0]


class ChromaRetriever:
    """Vector search with a persistent local Chroma collection."""

    name = "vector (Chroma + all-MiniLM-L6-v2)"

    def __init__(self, chunks: list[Chunk], persist_dir: Path = config.VECTOR_DIR):
        import chromadb  # imported lazily so tests don't need the model

        persist_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(persist_dir))
        self.col = client.get_or_create_collection("churn_docs", metadata={"hnsw:space": "cosine"})
        ids = [c.id for c in chunks]
        self.col.upsert(
            ids=ids,
            documents=[c.text for c in chunks],
            metadatas=[{"source": c.source, "heading": c.heading} for c in chunks],
        )
        stale = set(self.col.get()["ids"]) - set(ids)
        if stale:
            self.col.delete(ids=list(stale))
        self.by_id = {c.id: c for c in chunks}

    def search(self, query: str, k: int = 3) -> list[tuple[Chunk, float]]:
        res = self.col.query(query_texts=[query], n_results=k)
        return [
            (self.by_id[i], 1 - d) for i, d in zip(res["ids"][0], res["distances"][0])
        ]


_RETRIEVER = None


def get_retriever():
    """Build once per process. RETRIEVER=keyword forces the offline fallback."""
    global _RETRIEVER
    if _RETRIEVER is None:
        chunks = load_chunks()
        if os.getenv("RETRIEVER", "vector").lower() == "keyword":
            _RETRIEVER = KeywordRetriever(chunks)
        else:
            try:
                _RETRIEVER = ChromaRetriever(chunks)
            except Exception as exc:  # noqa: BLE001 - any embedding/setup failure
                print(f"[retriever] vector search unavailable ({exc}); using keyword search")
                _RETRIEVER = KeywordRetriever(chunks)
    return _RETRIEVER
