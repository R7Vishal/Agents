from __future__ import annotations

from dataclasses import asdict
import io
import subprocess
import threading
import uuid
import zipfile
from pathlib import Path
from typing import Any, Callable

from flask import Flask, jsonify, render_template, request, send_file

from ..composition import build_default_runtime
from ..orchestration.agent import CodingAgent
from ..reasoning import ModelRouter
from .chat_service import CopilotChatService


def create_app() -> Flask:
    app = Flask(__name__, template_folder="../templates")
    project_root = Path(__file__).resolve().parents[3]
    runtime = build_default_runtime(project_root)
    agent: CodingAgent = runtime.orchestrator
    chat_service: CopilotChatService = runtime.chat_service
    model_router: ModelRouter = runtime.model_router
    jobs: dict[str, dict[str, Any]] = {}
    jobs_lock = threading.Lock()

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/project-info")
    def project_info():
        return jsonify(
            {
                "ok": True,
                "project_root": str(project_root),
            }
        )

    @app.get("/api/ui/bootstrap")
    def ui_bootstrap():
        repo = str(request.args.get("repo", ".")).strip() or "."
        repo_path = _resolve_repo_path(repo)

        models = _model_status_payload()
        explorer = _build_project_explorer(repo_path)
        git_status = _git_status(repo_path)
        risk = _risk_indicator()

        return jsonify(
            {
                "ok": True,
                "project_root": str(project_root),
                "repo_path": str(repo_path),
                "models": models,
                "explorer": explorer,
                "git": git_status,
                "risk": risk,
            }
        )

    @app.get("/api/ui/diff-stats")
    def ui_diff_stats():
        repo = str(request.args.get("repo", ".")).strip() or "."
        repo_path = _resolve_repo_path(repo)
        diff_stats = _git_diff_stats(repo_path)
        return jsonify({"ok": True, "repo_path": str(repo_path), "diff_stats": diff_stats})

    @app.get("/api/download-project")
    def download_project():
        repo = str(request.args.get("repo", ".")).strip() or "."
        repo_path = _resolve_repo_path(repo)
        if not repo_path.exists() or not repo_path.is_dir():
            return jsonify({"ok": False, "error": "Invalid repo path"}), 400

        buffer = io.BytesIO()
        ignore_dirs = {".venv", "__pycache__", ".pytest_cache", ".git", "node_modules"}
        ignore_suffixes = {".pyc", ".pyo"}

        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for file_path in repo_path.rglob("*"):
                if not file_path.is_file():
                    continue
                rel = file_path.relative_to(repo_path)
                if any(part in ignore_dirs for part in rel.parts):
                    continue
                if file_path.suffix.lower() in ignore_suffixes:
                    continue
                archive.write(file_path, arcname=str(rel).replace("\\", "/"))

        buffer.seek(0)
        filename = f"{repo_path.name}-source.zip"
        return send_file(
            buffer,
            as_attachment=True,
            download_name=filename,
            mimetype="application/zip",
        )

    def _set_job(job_id: str, **values: Any) -> None:
        with jobs_lock:
            job = jobs.get(job_id)
            if not job:
                return
            if "detail" in values and values["detail"]:
                job["details"].append(str(values.pop("detail")))
            job.update(values)

    def _resolve_repo_path(repo: str) -> Path:
        repo_path = Path(repo)
        if not repo_path.is_absolute():
            repo_path = (project_root / repo_path).resolve()
        return repo_path

    def _model_status_payload() -> dict[str, Any]:
        router_models = [model_router.fast_local, model_router.main_local, model_router.cloud_fallback]
        registered = set(runtime.llm_gateway.registered_model_keys())
        active_route = model_router.recommend(prompt="workspace status", context_tokens=4096)

        items: list[dict[str, Any]] = []
        for model in router_models:
            integrated = model.key in registered
            provider_name = runtime.llm_gateway.provider_name_for(model.key)
            status = "integrated" if integrated else "not-integrated"
            if model.key == active_route.selected_model_key:
                status = "active-route"

            items.append(
                {
                    "key": model.key,
                    "label": model.label,
                    "role": model.role,
                    "local": model.local,
                    "estimated_vram_gb": model.estimated_vram_gb,
                    "integrated": integrated,
                    "provider": provider_name,
                    "status": status,
                }
            )

        integrated_count = sum(1 for item in items if item["integrated"])
        pending = integrated_count == 0

        return {
            "runtime": "local" if not model_router.policy.allow_cloud_fallback else "hybrid",
            "hardware": {
                "gpu_vram_gb": model_router.hardware.vram_gb,
                "ram_gb": model_router.hardware.system_ram_gb,
                "cpu": model_router.hardware.cpu,
                "context_tokens": model_router.policy.max_context_tokens,
            },
            "active_route": asdict(active_route),
            "items": items,
            "integration_status": {
                "pending": pending,
                "message": "Integration is pending with LLM" if pending else "LLM integration is active",
                "integrated_models": integrated_count,
            },
        }

    def _build_project_explorer(repo_path: Path) -> dict[str, Any]:
        folders: list[str] = []
        files: list[str] = []
        file_count = 0
        for path in repo_path.rglob("*"):
            parts = set(path.parts)
            if any(skip in parts for skip in {".git", ".venv", "node_modules", "__pycache__", ".agent_state", ".agent_logs"}):
                continue
            if path.is_file():
                file_count += 1
                if len(files) < 25:
                    files.append(str(path.relative_to(repo_path)).replace("\\", "/"))
            elif path.is_dir() and len(folders) < 20:
                folders.append(str(path.relative_to(repo_path)).replace("\\", "/"))

        selected = files[0] if files else ""
        related = files[1:4] if len(files) > 1 else []
        tests = [item for item in files if "test" in item.lower()][:6]
        docs = [item for item in files if item.lower().endswith(".md")][:6]

        context_tokens = min(max(file_count * 120, 1024), model_router.policy.max_context_tokens)

        return {
            "folders": sorted(folders)[:20],
            "files": files,
            "file_count": file_count,
            "selected": selected,
            "related": related,
            "tests": tests,
            "docs": docs,
            "context_tokens": context_tokens,
        }

    def _git_status(repo_path: Path) -> dict[str, Any]:
        if not (repo_path / ".git").exists():
            return {"available": False, "branch": "", "modified": [], "added": []}

        branch = ""
        modified: list[str] = []
        added: list[str] = []

        try:
            branch_proc = subprocess.run(
                "git branch --show-current",
                cwd=repo_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=20,
            )
            branch = branch_proc.stdout.strip()

            status_proc = subprocess.run(
                "git status --porcelain",
                cwd=repo_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=20,
            )
            for line in status_proc.stdout.splitlines():
                if len(line) < 4:
                    continue
                code = line[:2].strip()
                file_name = line[3:].strip()
                if "A" in code:
                    added.append(file_name)
                elif code:
                    modified.append(file_name)
        except Exception:
            return {"available": True, "branch": branch, "modified": [], "added": []}

        return {
            "available": True,
            "branch": branch,
            "modified": modified[:20],
            "added": added[:20],
        }

    def _git_diff_stats(repo_path: Path) -> dict[str, Any]:
        if not (repo_path / ".git").exists():
            return {
                "available": False,
                "totals": {
                    "files": 0,
                    "added_lines": 0,
                    "deleted_lines": 0,
                    "modified_files": 0,
                    "added_files": 0,
                    "untracked_files": 0,
                },
                "files": [],
            }

        unstaged = _run_git(repo_path, "git diff --numstat")
        staged = _run_git(repo_path, "git diff --numstat --cached")
        status_out = _run_git(repo_path, "git status --porcelain")

        file_stats: dict[str, dict[str, Any]] = {}
        status_map: dict[str, str] = {}

        if status_out["ok"]:
            for line in status_out["stdout"].splitlines():
                if len(line) < 4:
                    continue
                code = line[:2]
                path = line[3:].strip()
                if path:
                    status_map[path] = code

        for output in [unstaged, staged]:
            if not output["ok"]:
                continue
            for line in output["stdout"].splitlines():
                parts = line.split("\t")
                if len(parts) < 3:
                    continue
                added_raw, deleted_raw, path = parts[0], parts[1], parts[2]
                added = int(added_raw) if added_raw.isdigit() else 0
                deleted = int(deleted_raw) if deleted_raw.isdigit() else 0
                item = file_stats.setdefault(
                    path,
                    {
                        "path": path,
                        "added_lines": 0,
                        "deleted_lines": 0,
                        "change_type": "modified",
                    },
                )
                item["added_lines"] += added
                item["deleted_lines"] += deleted

        for path, code in status_map.items():
            code_clean = code.strip()
            item = file_stats.setdefault(
                path,
                {
                    "path": path,
                    "added_lines": 0,
                    "deleted_lines": 0,
                    "change_type": "modified",
                },
            )
            if code_clean.startswith("??"):
                item["change_type"] = "untracked"
                file_path = repo_path / path
                try:
                    if file_path.exists() and file_path.is_file():
                        item["added_lines"] = max(item["added_lines"], len(file_path.read_text(encoding="utf-8", errors="ignore").splitlines()))
                except OSError:
                    pass
            elif "A" in code_clean:
                item["change_type"] = "added"
            else:
                item["change_type"] = "modified"

        files = sorted(file_stats.values(), key=lambda row: (row["path"]))
        totals = {
            "files": len(files),
            "added_lines": sum(int(row["added_lines"]) for row in files),
            "deleted_lines": sum(int(row["deleted_lines"]) for row in files),
            "modified_files": sum(1 for row in files if row["change_type"] == "modified"),
            "added_files": sum(1 for row in files if row["change_type"] == "added"),
            "untracked_files": sum(1 for row in files if row["change_type"] == "untracked"),
        }

        return {
            "available": True,
            "totals": totals,
            "files": files[:100],
        }

    def _run_git(repo_path: Path, command: str) -> dict[str, Any]:
        try:
            proc = subprocess.run(
                command,
                cwd=repo_path,
                shell=True,
                capture_output=True,
                text=True,
                timeout=20,
            )
            return {"ok": proc.returncode == 0, "stdout": proc.stdout, "stderr": proc.stderr}
        except Exception as exc:
            return {"ok": False, "stdout": "", "stderr": str(exc)}

    def _risk_indicator() -> dict[str, Any]:
        return {
            "read_files": "low",
            "run_tests": "low",
            "modify_source": "medium",
            "install_package": "medium",
            "delete_files": "high",
            "execute_shell": "high",
            "git_push": "high",
            "permissions": {
                "read_files": True,
                "modify_source": True,
                "run_tests": True,
                "install_dependencies": False,
                "delete_files": False,
                "git_commit": False,
                "git_push": False,
            },
        }

    def _resolve_output_path(output: str) -> Path:
        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = project_root / output_path
        return output_path

    def _build_requirement(
        prompt: str,
        attachments: list[dict[str, str]] | None,
        context_paths: list[str] | None,
        repo_path: Path,
    ) -> str:
        sections: list[str] = [prompt]

        if attachments:
            for item in attachments[:10]:
                name = str(item.get("name", "uploaded_file"))
                content = str(item.get("content", ""))
                if not content:
                    continue
                sections.append(f"\n\n[ATTACHMENT: {name}]\n{content[:200000]}")

        if context_paths:
            for raw_path in context_paths[:20]:
                file_path = Path(str(raw_path).strip())
                if not file_path:
                    continue
                if not file_path.is_absolute():
                    file_path = (repo_path / file_path).resolve()
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")[:200000]
                    sections.append(f"\n\n[CONTEXT FILE: {file_path}]\n{content}")
                except Exception as exc:
                    sections.append(f"\n\n[CONTEXT FILE READ ERROR: {file_path}]\n{exc}")

        return "".join(sections)

    def _infer_action(prompt: str, selected_mode: str, execute_mode: bool) -> str | None:
        mode = selected_mode.strip().lower()
        text = prompt.strip().lower()

        if execute_mode and mode in {"first-run", "run-plan"}:
            return mode

        if text.startswith("/run"):
            if "run-plan" in text:
                return "run-plan"
            if "first-run" in text or "first run" in text:
                return "first-run"
            if mode in {"first-run", "run-plan"}:
                return mode

        if "run-plan" in text or "run plan" in text or "execute plan" in text:
            return "run-plan"
        if "first-run" in text or "first run" in text:
            return "first-run"
        return None

    def _run_first_run(payload: dict[str, Any]) -> dict[str, Any]:
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("Prompt is required.")

        repo = str(payload.get("repo", ".")).strip() or "."
        run_baseline = bool(payload.get("run_baseline", False))
        output = str(payload.get("output", "")).strip()
        attachments = payload.get("attachments") or []
        context_paths = payload.get("context_paths") or []

        repo_path = _resolve_repo_path(repo)
        requirement = _build_requirement(
            prompt=prompt,
            attachments=attachments,
            context_paths=context_paths,
            repo_path=repo_path,
        )

        report = agent.first_run_assessment(
            repo_path=repo_path,
            requirement=requirement,
            run_baseline=run_baseline,
        )

        saved_path = ""
        if output:
            output_path = _resolve_output_path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report, encoding="utf-8")
            saved_path = str(output_path)

        return {
            "ok": True,
            "report": report,
            "saved_path": saved_path,
            "repo": str(repo_path),
        }

    def _run_plan(payload: dict[str, Any]) -> dict[str, Any]:
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            raise ValueError("Prompt is required.")

        repo = str(payload.get("repo", ".")).strip() or "."
        plan_file = str(payload.get("plan_file", "")).strip()
        if not plan_file:
            raise ValueError("plan_file is required.")

        output = str(payload.get("output", "")).strip()
        max_repair_attempts_per_task = int(payload.get("max_repair_attempts_per_task", 2) or 2)
        sandbox_profile = str(payload.get("sandbox_profile", "local") or "local").strip().lower()
        scoped_write_paths = [str(item).strip() for item in list(payload.get("scoped_write_paths", []) or []) if str(item).strip()]
        require_approval = bool(payload.get("require_approval", False))
        approved_actions = [str(item).strip() for item in list(payload.get("approved_actions", []) or []) if str(item).strip()]
        run_validation_pipeline = bool(payload.get("run_validation_pipeline", False))
        validation_retries_per_stage = int(payload.get("validation_retries_per_stage", 1) or 1)
        resume_run_id_raw = str(payload.get("resume_run_id", "")).strip()
        resume_run_id = resume_run_id_raw or None
        resume_latest = bool(payload.get("resume_latest", False))
        resume_dry_run = bool(payload.get("resume_dry_run", False))
        resume_max_risk = int(payload.get("resume_max_risk", 5) or 5)
        attachments = payload.get("attachments") or []
        context_paths = payload.get("context_paths") or []

        repo_path = _resolve_repo_path(repo)
        plan_path = Path(plan_file)
        if not plan_path.is_absolute():
            plan_path = (project_root / plan_path).resolve()

        requirement = _build_requirement(
            prompt=prompt,
            attachments=attachments,
            context_paths=context_paths,
            repo_path=repo_path,
        )

        report = agent.run_controlled_plan(
            repo_path=repo_path,
            requirement=requirement,
            plan_file=plan_path,
            max_repair_attempts_per_task=max_repair_attempts_per_task,
            sandbox_profile=sandbox_profile,
            scoped_write_paths=scoped_write_paths,
            require_approval=require_approval,
            approved_actions=approved_actions,
            run_validation_pipeline=run_validation_pipeline,
            validation_retries_per_stage=validation_retries_per_stage,
            resume_run_id=resume_run_id,
            resume_latest=resume_latest,
            resume_dry_run=resume_dry_run,
            resume_max_risk=resume_max_risk,
        )

        saved_path = ""
        if output:
            output_path = _resolve_output_path(output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(report, encoding="utf-8")
            saved_path = str(output_path)

        return {
            "ok": True,
            "report": report,
            "saved_path": saved_path,
            "repo": str(repo_path),
            "plan_file": str(plan_path),
        }

    def _start_async_job(label: str, payload: dict[str, Any], executor: Callable[[dict[str, Any]], dict[str, Any]]) -> str:
        job_id = str(uuid.uuid4())
        with jobs_lock:
            jobs[job_id] = {
                "id": job_id,
                "label": label,
                "status": "queued",
                "progress": 0,
                "message": "Queued",
                "details": [f"{label}: job queued"],
                "result": None,
                "error": "",
            }

        def _worker() -> None:
            try:
                _set_job(job_id, status="running", progress=10, message="Preparing inputs", detail="Preparing request payload")
                _set_job(job_id, progress=30, message="Analyzing request", detail="Resolving repository and parameters")
                _set_job(job_id, progress=55, message="Executing agent workflow", detail="Running agent execution")
                result = executor(payload)
                _set_job(job_id, progress=90, message="Finalizing output", detail="Building response report")
                _set_job(job_id, status="completed", progress=100, message="Completed", detail="Execution completed", result=result)
            except Exception as exc:
                _set_job(job_id, status="failed", progress=100, message="Failed", detail=f"Error: {exc}", error=str(exc))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()
        return job_id

    @app.post("/api/chat")
    def chat():
        payload = request.get_json(silent=True) or {}
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            return jsonify({"ok": False, "error": "Prompt is required."}), 400

        session_id = str(payload.get("session_id", "")).strip() or str(uuid.uuid4())
        repo = str(payload.get("repo", ".")).strip() or "."
        selected_mode = str(payload.get("mode", "first-run")).strip() or "first-run"
        plan_file = str(payload.get("plan_file", "")).strip()
        execute_mode = bool(payload.get("execute_mode", False))
        action = _infer_action(prompt=prompt, selected_mode=selected_mode, execute_mode=execute_mode)

        repo_path = _resolve_repo_path(repo)
        chat_result = chat_service.reply(
            session_id=session_id,
            prompt=prompt,
            repo_path=repo_path,
            selected_mode=selected_mode,
            plan_file=plan_file,
            action=action,
        )

        integration_status = _model_status_payload()["integration_status"]

        response: dict[str, Any] = {
            "ok": True,
            "session_id": chat_result["session_id"],
            "reply": chat_result["reply"],
            "message_count": chat_result["message_count"],
            "action": action,
            "integration_note": integration_status["message"],
        }

        if integration_status["pending"] and not action:
            response["reply"] = f"{response['reply']}\n\nIntegration is pending with LLM"

        if not action:
            return jsonify(response)

        run_payload = dict(payload)
        run_payload["prompt"] = prompt

        if action == "run-plan" and not plan_file:
            response["ok"] = False
            response["error"] = "plan_file is required for run-plan execution."
            return jsonify(response), 400

        if bool(payload.get("async_mode", True)):
            executor = _run_first_run if action == "first-run" else _run_plan
            job_id = _start_async_job(action, run_payload, executor)
            response["job_id"] = job_id
            response["job_status"] = "queued"
            return jsonify(response)

        try:
            result = _run_first_run(run_payload) if action == "first-run" else _run_plan(run_payload)
            response["result"] = result
            return jsonify(response)
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), **response}), 400

    @app.post("/api/reasoning/route")
    def reasoning_route():
        payload = request.get_json(silent=True) or {}
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            return jsonify({"ok": False, "error": "Prompt is required."}), 400

        context_tokens = int(payload.get("context_tokens", 0) or 0)
        decision = model_router.recommend(prompt=prompt, context_tokens=context_tokens)
        return jsonify({"ok": True, "decision": asdict(decision)})

    @app.post("/api/first-run")
    def first_run():
        payload = request.get_json(silent=True) or {}
        if bool(payload.get("async_mode", False)):
            job_id = _start_async_job("first-run", payload, _run_first_run)
            return jsonify({"ok": True, "job_id": job_id})

        try:
            return jsonify(_run_first_run(payload))
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.post("/api/run-plan")
    def run_plan():
        payload = request.get_json(silent=True) or {}
        if bool(payload.get("async_mode", False)):
            job_id = _start_async_job("run-plan", payload, _run_plan)
            return jsonify({"ok": True, "job_id": job_id})

        try:
            return jsonify(_run_plan(payload))
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.get("/api/job/<job_id>")
    def get_job(job_id: str):
        with jobs_lock:
            job = jobs.get(job_id)
            if not job:
                return jsonify({"ok": False, "error": "Job not found"}), 404
            return jsonify({"ok": True, "job": job})

    @app.post("/api/rotate-key")
    def rotate_key():
        result = agent.rotate_checkpoint_key()
        return jsonify({"ok": True, "rotation": result})

    return app


def main() -> None:
    app = create_app()
    app.run(host="127.0.0.1", port=5050, debug=False)


if __name__ == "__main__":
    main()
