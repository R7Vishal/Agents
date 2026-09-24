from pathlib import Path

from coding_agent.retrieval import LocalCodeSearchAdapter


def test_symbol_and_semantic_search(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    file_path = repo / "service.py"
    file_path.write_text(
        """
class OrderService:
    def calculate_total(self, amount: int) -> int:
        return amount * 2
""".strip(),
        encoding="utf-8",
    )

    adapter = LocalCodeSearchAdapter(repo)

    symbol_hits = adapter.symbol_search("calculate_total")
    assert symbol_hits
    assert symbol_hits[0].file_path == "service.py"

    semantic_hits = adapter.semantic_search("calculate order total")
    assert semantic_hits
    assert semantic_hits[0].file_path == "service.py"
