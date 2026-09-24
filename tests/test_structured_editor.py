from pathlib import Path

from coding_agent.editing import StructuredEditor


def test_structured_editor_replace_and_rollback(tmp_path: Path) -> None:
    editor = StructuredEditor(tmp_path)
    target = tmp_path / "sample.txt"
    target.write_text("hello old world", encoding="utf-8")

    replace_result = editor.replace_text(target, "old", "new")
    assert replace_result.ok
    assert "new" in target.read_text(encoding="utf-8")

    checkpoint_id = str(replace_result.metadata["checkpoint_id"])
    rollback_result = editor.rollback(checkpoint_id)
    assert rollback_result.ok
    assert target.read_text(encoding="utf-8") == "hello old world"
