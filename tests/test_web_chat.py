from pathlib import Path
import subprocess

from coding_agent.web_app import create_app


def test_chat_returns_conversational_reply(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("sample repo\n", encoding="utf-8")

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/chat",
        json={
            "prompt": "hello",
            "repo": str(repo),
            "mode": "first-run",
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["session_id"]
    assert "reply" in data
    assert data.get("action") is None
    assert data.get("integration_note") == "Integration is pending with LLM"
    assert "Integration is pending with LLM" in data["reply"]


def test_chat_can_trigger_first_run_job(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("sample repo\n", encoding="utf-8")

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/chat",
        json={
            "prompt": "run first-run now",
            "repo": str(repo),
            "mode": "first-run",
            "execute_mode": True,
            "async_mode": True,
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["action"] == "first-run"
    assert data.get("job_id")

    job_response = client.get(f"/api/job/{data['job_id']}")
    assert job_response.status_code == 200
    job_data = job_response.get_json()
    assert job_data["ok"] is True
    assert job_data["job"]["status"] in {"queued", "running", "completed"}


def test_reasoning_route_endpoint(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("sample repo\n", encoding="utf-8")

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/reasoning/route",
        json={
            "prompt": "Explain this DTO",
            "context_tokens": 2048,
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["decision"]["selected_model_key"] in {"qwen2.5-coder-3b-q4", "qwen2.5-coder-7b-q4"}


def test_ui_bootstrap_exposes_pending_llm_integration(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    app = create_app()
    client = app.test_client()

    response = client.get(f"/api/ui/bootstrap?repo={repo}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["models"]["items"]
    assert any(item["status"] == "active-route" for item in data["models"]["items"])
    assert data["git"]["available"] is False
    assert data["models"]["integration_status"]["pending"] is True
    assert data["models"]["integration_status"]["message"] == "Integration is pending with LLM"


def test_chat_returns_pending_note_and_can_trigger_job(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    app = create_app()
    client = app.test_client()

    response = client.post(
        "/api/chat",
        json={
            "prompt": "run first-run now",
            "repo": str(repo),
            "mode": "first-run",
            "execute_mode": True,
            "async_mode": True,
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["integration_note"] == "Integration is pending with LLM"
    assert data["action"] == "first-run"
    assert data.get("job_id")


def test_ui_diff_stats_non_git_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("sample repo\n", encoding="utf-8")

    app = create_app()
    client = app.test_client()

    response = client.get(f"/api/ui/diff-stats?repo={repo}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["diff_stats"]["available"] is False
    assert data["diff_stats"]["totals"]["files"] == 0


def test_ui_diff_stats_git_repo_changes(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True, text=True)

    tracked = repo / "tracked.txt"
    tracked.write_text("line1\nline2\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True, capture_output=True, text=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True, text=True)

    tracked.write_text("line1\nline2\nline3\n", encoding="utf-8")
    untracked = repo / "new.txt"
    untracked.write_text("a\nb\n", encoding="utf-8")

    app = create_app()
    client = app.test_client()

    response = client.get(f"/api/ui/diff-stats?repo={repo}")
    assert response.status_code == 200
    data = response.get_json()
    assert data["ok"] is True
    assert data["diff_stats"]["available"] is True
    assert data["diff_stats"]["totals"]["files"] >= 1
    assert any(item["path"].endswith("tracked.txt") for item in data["diff_stats"]["files"])
