from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TOKEN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


@dataclass(frozen=True)
class SemanticDocument:
    path: str
    tokens: dict[str, int]
    total_terms: int


class PersistentSemanticIndex:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.index_path = workspace_root / ".agent_state" / "semantic_index.json"
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._index: dict[str, Any] = {"documents": {}, "meta": {}}
        self._loaded = False

    def build(self, root: Path | None = None, max_file_size_bytes: int = 1_000_000) -> dict[str, Any]:
        base = (root or self.workspace_root).resolve()
        documents: dict[str, dict[str, Any]] = {}
        file_count = 0

        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if any(part in {".git", ".venv", "__pycache__", "node_modules", ".agent_state", ".agent_logs"} for part in path.parts):
                continue
            try:
                if path.stat().st_size > max_file_size_bytes:
                    continue
            except OSError:
                continue

            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            tokens = TOKEN_PATTERN.findall(text.lower())
            if not tokens:
                continue
            expanded_tokens: list[str] = []
            for token in tokens:
                expanded_tokens.append(token)
                if "_" in token:
                    expanded_tokens.extend([part for part in token.split("_") if len(part) >= 3])

            counts = Counter(expanded_tokens)
            rel = str(path.relative_to(self.workspace_root)).replace("\\", "/")
            documents[rel] = {
                "tokens": dict(counts),
                "total_terms": sum(counts.values()),
                "mtime_ns": path.stat().st_mtime_ns,
            }
            file_count += 1

        self._index = {
            "documents": documents,
            "meta": {
                "workspace": str(self.workspace_root),
                "file_count": file_count,
            },
        }
        self._save()
        self._loaded = True
        return {"success": True, "indexed_files": file_count, "index_path": str(self.index_path)}

    def search(self, query: str, max_results: int = 100) -> list[dict[str, Any]]:
        self._ensure_loaded()
        terms = [term.lower() for term in TOKEN_PATTERN.findall(query)]
        if not terms:
            return []

        idf = self._compute_idf()
        scored: list[tuple[str, float]] = []
        for path, doc in self._index.get("documents", {}).items():
            token_map = doc.get("tokens", {})
            total_terms = max(int(doc.get("total_terms", 1) or 1), 1)
            score = 0.0
            matched = False
            for term in terms:
                tf = int(token_map.get(term, 0)) / total_terms
                if tf > 0:
                    matched = True
                score += tf * idf.get(term, 0.0)
            if matched and score > 0:
                scored.append((path, score))

        scored.sort(key=lambda item: item[1], reverse=True)
        results: list[dict[str, Any]] = []
        for path, score in scored[:max_results]:
            results.append({"path": path, "score": round(score, 6)})
        return results

    def is_ready(self) -> bool:
        self._ensure_loaded()
        return bool(self._index.get("documents"))

    def _compute_idf(self) -> dict[str, float]:
        docs = self._index.get("documents", {})
        total_docs = max(len(docs), 1)
        df: Counter[str] = Counter()
        for doc in docs.values():
            tokens = doc.get("tokens", {})
            for term in tokens.keys():
                df[str(term)] += 1

        idf: dict[str, float] = {}
        for term, count in df.items():
            idf[term] = math.log((1 + total_docs) / (1 + count)) + 1.0
        return idf

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        if not self.index_path.exists():
            self._index = {"documents": {}, "meta": {}}
            self._loaded = True
            return
        try:
            self._index = json.loads(self.index_path.read_text(encoding="utf-8"))
            if not isinstance(self._index, dict):
                self._index = {"documents": {}, "meta": {}}
        except Exception:
            self._index = {"documents": {}, "meta": {}}
        self._loaded = True

    def _save(self) -> None:
        self.index_path.write_text(json.dumps(self._index, ensure_ascii=False), encoding="utf-8")
