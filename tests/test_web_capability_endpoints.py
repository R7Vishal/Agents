from pathlib import Path

from coding_agent.presentation.web_app import create_app


def test_capability_endpoints(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    app = create_app()
    client = app.test_client()

    tools_response = client.get("/api/tools")
    assert tools_response.status_code == 200
    tools_data = tools_response.get_json()
    assert tools_data["ok"] is True
    assert any(item["name"] == "read_file" for item in tools_data["tools"])

    cap_response = client.get("/api/capabilities")
    assert cap_response.status_code == 200
    cap_data = cap_response.get_json()
    assert cap_data["ok"] is True
    assert "file_operations" in cap_data["capabilities"]

    doctor_response = client.get("/api/doctor")
    assert doctor_response.status_code == 200
    doctor_data = doctor_response.get_json()
    assert doctor_data["ok"] is True
    assert "health" in doctor_data["doctor"]

    status_response = client.get("/api/status")
    assert status_response.status_code == 200
    status_data = status_response.get_json()
    assert status_data["ok"] is True
    assert "tool_count" in status_data
    assert "execution_mode" in status_data

    index_response = client.post("/api/index/rebuild")
    assert index_response.status_code == 200
    index_data = index_response.get_json()
    assert index_data["ok"] is True

    request_response = client.post(
        "/api/approvals/request",
        json={"action": "delete_file", "details": "test"},
    )
    assert request_response.status_code == 200
    request_data = request_response.get_json()
    assert request_data["ok"] is True
    request_id = request_data["result"]["request_id"]

    approve_response = client.post(
        "/api/approvals/approve",
        json={"request_id": request_id},
    )
    assert approve_response.status_code == 200
    approve_data = approve_response.get_json()
    assert approve_data["ok"] is True
    assert approve_data["result"]["approval_token"]

    list_response = client.get("/api/approvals")
    assert list_response.status_code == 200
    list_data = list_response.get_json()
    assert list_data["ok"] is True
    assert list_data["result"]["requests"]

    telemetry_response = client.get("/api/reasoning/telemetry")
    assert telemetry_response.status_code == 200
    telemetry_data = telemetry_response.get_json()
    assert telemetry_data["ok"] is True

    guide_response = client.get("/guide")
    assert guide_response.status_code == 200
    assert b"Coding Agent Guide" in guide_response.data

    acceptance_dry_response = client.post("/api/acceptance/run", json={"execute": False})
    assert acceptance_dry_response.status_code == 200
    acceptance_dry_data = acceptance_dry_response.get_json()
    assert acceptance_dry_data["ok"] is True
    assert acceptance_dry_data["executed"] is False
    assert acceptance_dry_data["report_url"] == "/api/acceptance/report"

    acceptance_report_response = client.get("/api/acceptance/report")
    assert acceptance_report_response.status_code in {200, 404}
