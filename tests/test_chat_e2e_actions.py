from pathlib import Path
import subprocess

from coding_agent.presentation.web_app import create_app


def test_chat_end_to_end_file_and_capabilities_flow(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("sample\n", encoding="utf-8")

    app = create_app()
    client = app.test_client()

    response1 = client.post(
        "/api/chat",
        json={
            "prompt": "What are your current capabilities?",
            "repo": str(repo),
            "mode": "first-run",
        },
    )
    assert response1.status_code == 200
    data1 = response1.get_json()
    assert data1["ok"] is True
    assert "CODING AGENT CAPABILITIES" in data1["reply"]

    response2 = client.post(
        "/api/chat",
        json={
            "prompt": "How can I improve you?",
            "repo": str(repo),
            "mode": "first-run",
        },
    )
    assert response2.status_code == 200
    data2 = response2.get_json()
    assert data2["ok"] is True
    assert "AGENT IMPROVEMENT ADVISOR" in data2["reply"]


def test_chat_git_changed_flow(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True, text=True)

    tracked = repo / "tracked.txt"
    tracked.write_text("line1\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, text=True)
    tracked.write_text("line1\nline2\n", encoding="utf-8")

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/chat",
        json={
            "prompt": "Show me what changed in Git",
            "repo": str(repo),
            "mode": "first-run",
        },
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert "GIT CHANGES" in data["reply"]
