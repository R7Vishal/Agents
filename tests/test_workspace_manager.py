from pathlib import Path

from coding_agent.workspace_manager import WorkspaceAccessError, WorkspaceManager


def test_workspace_manager_crud_and_search(tmp_path: Path) -> None:
    manager = WorkspaceManager(tmp_path)

    created = manager.create_file("notes/hello.md", "hello project")
    assert created["success"] is True

    read = manager.read_file("notes/hello.md")
    assert read["success"] is True
    assert "hello project" in str(read["content"])

    edited = manager.edit_file("notes/hello.md", old_text="project", new_text="workspace")
    assert edited["success"] is True

    renamed = manager.rename_file("notes/hello.md", "notes/hello-renamed.md")
    assert renamed["success"] is True

    listing = manager.list_directory("notes")
    assert listing["success"] is True
    assert any(item["name"] == "hello-renamed.md" for item in listing["items"])

    search_files = manager.search_files("*.md")
    assert search_files["success"] is True
    assert "notes/hello-renamed.md" in search_files["matches"]

    search_text = manager.search_text("workspace")
    assert search_text["success"] is True
    assert search_text["count"] >= 1

    deleted = manager.delete_file("notes/hello-renamed.md")
    assert deleted["success"] is True


def test_workspace_manager_blocks_path_traversal(tmp_path: Path) -> None:
    manager = WorkspaceManager(tmp_path)

    try:
        manager.read_file("../outside.txt")
        assert False, "Expected path traversal to be blocked"
    except WorkspaceAccessError:
        assert True
