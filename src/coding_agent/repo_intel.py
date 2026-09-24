from __future__ import annotations

from pathlib import Path

from .models import RepositoryFacts


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def discover_repository(repo_path: Path) -> RepositoryFacts:
    facts = RepositoryFacts(repo_path=str(repo_path))

    file_index = [p for p in repo_path.rglob("*") if p.is_file()]

    for path in file_index:
        rel = _rel(path, repo_path)
        name = path.name.lower()

        if name in {"main.py", "app.py", "manage.py", "index.js", "server.js"}:
            facts.entry_points.append(rel)
        if name in {
            "requirements.txt",
            "pyproject.toml",
            "package.json",
            "pom.xml",
            "build.gradle",
            "manifest.yml",
        }:
            facts.package_manifests.append(rel)
        if "test" in name or "/tests/" in f"/{rel}/":
            facts.test_files.append(rel)
        if ".github/workflows/" in f"/{rel}":
            facts.workflows.append(rel)
        if name.startswith("docker") or name == "docker-compose.yml":
            facts.docker_files.append(rel)
        if "prompt" in name:
            facts.prompts.append(rel)
        if "plan" in name or "planner" in name:
            facts.planner_files.append(rel)
        if "lifecycle" in name or "state" in name:
            facts.lifecycle_files.append(rel)
        if "safety" in name or "guard" in name or "invariant" in name:
            facts.safety_files.append(rel)
        if "persist" in name or "store" in name or "state" in name:
            facts.persistence_files.append(rel)

    todo_markers: list[str] = []
    for path in file_index:
        suffix = path.suffix.lower()
        if suffix not in {".py", ".md", ".txt", ".yml", ".yaml", ".json", ".js", ".ts"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        if "TODO" in text or "FIXME" in text:
            todo_markers.append(_rel(path, repo_path))
    facts.todo_markers = sorted(set(todo_markers))

    facts.entry_points = sorted(set(facts.entry_points))
    facts.package_manifests = sorted(set(facts.package_manifests))
    facts.test_files = sorted(set(facts.test_files))
    facts.workflows = sorted(set(facts.workflows))
    facts.docker_files = sorted(set(facts.docker_files))
    facts.prompts = sorted(set(facts.prompts))
    facts.planner_files = sorted(set(facts.planner_files))
    facts.lifecycle_files = sorted(set(facts.lifecycle_files))
    facts.safety_files = sorted(set(facts.safety_files))
    facts.persistence_files = sorted(set(facts.persistence_files))
    return facts
