from pathlib import Path

from coding_agent.retrieval import PersistentSemanticIndex


def test_persistent_semantic_index_build_and_search(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "auth_service.py").write_text(
        "def authenticate_user(token):\n    return token == 'ok'\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "orders.py").write_text(
        "def calculate_order_total(amount):\n    return amount * 2\n",
        encoding="utf-8",
    )

    index = PersistentSemanticIndex(tmp_path)
    result = index.build()
    assert result["success"] is True
    assert result["indexed_files"] >= 2

    hits = index.search("authenticate user token")
    assert hits
    assert any(item["path"].endswith("auth_service.py") for item in hits)

    index_reload = PersistentSemanticIndex(tmp_path)
    persisted_hits = index_reload.search("order total")
    assert persisted_hits
