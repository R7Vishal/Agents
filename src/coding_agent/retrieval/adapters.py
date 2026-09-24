from __future__ import annotations

import re
from pathlib import Path

from ..layers.contracts import SearchHit


class LocalCodeSearchAdapter:
    def __init__(self, repo_path: Path, max_file_size_bytes: int = 1_000_000) -> None:
        self.repo_path = repo_path
        self.max_file_size_bytes = max_file_size_bytes

    def file_search(self, query: str) -> list[SearchHit]:
        normalized = query.strip().lower()
        if not normalized:
            return []

        hits: list[SearchHit] = []
        for file_path in self._iter_files():
            rel = str(file_path.relative_to(self.repo_path)).replace("\\", "/")
            if normalized in rel.lower():
                hits.append(SearchHit(file_path=rel, snippet=rel, score=1.0, symbol=""))
        return hits[:100]

    def symbol_search(self, symbol: str) -> list[SearchHit]:
        normalized = symbol.strip()
        if not normalized:
            return []

        symbol_pattern = re.compile(rf"\b{re.escape(normalized)}\b")
        definition_pattern = re.compile(
            rf"\b(def|class|function|interface|type)\s+{re.escape(normalized)}\b"
        )
        hits: list[SearchHit] = []

        for file_path in self._iter_files():
            content = self._read_file(file_path)
            if not content:
                continue

            score = 0.0
            snippet = ""
            if definition_pattern.search(content):
                score = 1.0
                snippet = self._extract_snippet(content, definition_pattern.search(content).start())
            elif symbol_pattern.search(content):
                score = 0.8
                snippet = self._extract_snippet(content, symbol_pattern.search(content).start())

            if score > 0:
                hits.append(
                    SearchHit(
                        file_path=str(file_path.relative_to(self.repo_path)).replace("\\", "/"),
                        snippet=snippet,
                        score=score,
                        symbol=normalized,
                    )
                )

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:100]

    def semantic_search(self, query: str) -> list[SearchHit]:
        terms = [term for term in re.split(r"\W+", query.lower()) if len(term) >= 3]
        if not terms:
            return []

        hits: list[SearchHit] = []
        for file_path in self._iter_files():
            content = self._read_file(file_path)
            if not content:
                continue

            lowered = content.lower()
            matches = [term for term in terms if term in lowered]
            if not matches:
                continue

            score = len(matches) / max(len(terms), 1)
            anchor = lowered.find(matches[0])
            snippet = self._extract_snippet(content, anchor)
            hits.append(
                SearchHit(
                    file_path=str(file_path.relative_to(self.repo_path)).replace("\\", "/"),
                    snippet=snippet,
                    score=round(score, 4),
                    symbol="",
                )
            )

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:100]

    def dependency_search(self, symbol: str) -> list[SearchHit]:
        normalized = symbol.strip()
        if not normalized:
            return []

        import_pattern = re.compile(rf"\b(import|from|require)\b[^\n]*\b{re.escape(normalized)}\b")
        hits: list[SearchHit] = []
        for file_path in self._iter_files():
            content = self._read_file(file_path)
            if not content:
                continue
            match = import_pattern.search(content)
            if not match:
                continue
            hits.append(
                SearchHit(
                    file_path=str(file_path.relative_to(self.repo_path)).replace("\\", "/"),
                    snippet=self._extract_snippet(content, match.start()),
                    score=1.0,
                    symbol=normalized,
                )
            )
        return hits[:100]

    def call_graph(self, symbol: str) -> list[SearchHit]:
        normalized = symbol.strip()
        if not normalized:
            return []

        call_pattern = re.compile(rf"\b{re.escape(normalized)}\s*\(")
        definition_pattern = re.compile(rf"\b(def|function)\s+{re.escape(normalized)}\b")
        hits: list[SearchHit] = []
        for file_path in self._iter_files():
            content = self._read_file(file_path)
            if not content:
                continue

            for match in call_pattern.finditer(content):
                prefix = content[max(0, match.start() - 40) : match.start()]
                if definition_pattern.search(prefix):
                    continue
                hits.append(
                    SearchHit(
                        file_path=str(file_path.relative_to(self.repo_path)).replace("\\", "/"),
                        snippet=self._extract_snippet(content, match.start()),
                        score=0.9,
                        symbol=normalized,
                    )
                )
                if len(hits) >= 100:
                    return hits
        return hits

    def _iter_files(self):
        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue
            if any(part in {".git", ".venv", "node_modules", "__pycache__", ".agent_state", ".agent_logs"} for part in file_path.parts):
                continue
            try:
                if file_path.stat().st_size > self.max_file_size_bytes:
                    continue
            except OSError:
                continue
            yield file_path

    def _read_file(self, file_path: Path) -> str:
        try:
            return file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return ""

    def _extract_snippet(self, content: str, anchor: int, radius: int = 160) -> str:
        start = max(0, anchor - radius)
        end = min(len(content), anchor + radius)
        return content[start:end].replace("\r", " ").replace("\n", " ").strip()
