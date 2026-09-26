from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
import re


class WorkspaceAccessError(RuntimeError):
    pass


class WorkspaceManager:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()

    def resolve_path(self, raw_path: str) -> Path:
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (self.workspace_root / candidate).resolve()
        else:
            candidate = candidate.resolve()

        if not self._is_within_workspace(candidate):
            raise WorkspaceAccessError(f"Path is outside workspace: {raw_path}")
        return candidate

    def list_directory(self, raw_path: str = ".") -> dict[str, object]:
        path = self.resolve_path(raw_path)
        if not path.exists() or not path.is_dir():
            return {
                "success": False,
                "operation": "list_directory",
                "path": str(path),
                "error": "Directory does not exist",
            }

        children: list[dict[str, object]] = []
        for child in sorted(path.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            children.append(
                {
                    "name": child.name,
                    "path": self.to_relative_path(child),
                    "is_dir": child.is_dir(),
                    "size": child.stat().st_size if child.is_file() else 0,
                }
            )

        return {
            "success": True,
            "operation": "list_directory",
            "path": self.to_relative_path(path),
            "items": children,
            "count": len(children),
        }

    def read_file(self, raw_path: str, encoding: str = "utf-8") -> dict[str, object]:
        path = self.resolve_path(raw_path)
        if not path.exists() or not path.is_file():
            return {
                "success": False,
                "operation": "read_file",
                "path": self.to_relative_path(path),
                "error": "File does not exist",
            }

        content = path.read_text(encoding=encoding, errors="ignore")
        return {
            "success": True,
            "operation": "read_file",
            "path": self.to_relative_path(path),
            "content": content,
            "bytes": len(content.encode("utf-8", errors="ignore")),
        }

    def write_file(self, raw_path: str, content: str, encoding: str = "utf-8") -> dict[str, object]:
        path = self.resolve_path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)
        return {
            "success": True,
            "operation": "write_file",
            "path": self.to_relative_path(path),
            "bytes_written": len(content.encode("utf-8", errors="ignore")),
        }

    def create_file(self, raw_path: str, content: str = "", encoding: str = "utf-8", overwrite: bool = False) -> dict[str, object]:
        path = self.resolve_path(raw_path)
        if path.exists() and not overwrite:
            return {
                "success": False,
                "operation": "create_file",
                "path": self.to_relative_path(path),
                "error": "File already exists; pass overwrite=true to replace",
            }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)
        return {
            "success": True,
            "operation": "create_file",
            "path": self.to_relative_path(path),
            "bytes_written": len(content.encode("utf-8", errors="ignore")),
        }

    def edit_file(
        self,
        raw_path: str,
        old_text: str | None = None,
        new_text: str | None = None,
        content: str | None = None,
        encoding: str = "utf-8",
    ) -> dict[str, object]:
        path = self.resolve_path(raw_path)
        if not path.exists() or not path.is_file():
            return {
                "success": False,
                "operation": "edit_file",
                "path": self.to_relative_path(path),
                "error": "File does not exist",
            }

        original = path.read_text(encoding=encoding, errors="ignore")
        updated = original

        if content is not None:
            updated = content
        elif old_text is not None and new_text is not None:
            if old_text not in original:
                return {
                    "success": False,
                    "operation": "edit_file",
                    "path": self.to_relative_path(path),
                    "error": "old_text was not found in file",
                }
            updated = original.replace(old_text, new_text, 1)
        else:
            return {
                "success": False,
                "operation": "edit_file",
                "path": self.to_relative_path(path),
                "error": "Provide either content or both old_text/new_text",
            }

        path.write_text(updated, encoding=encoding)
        return {
            "success": True,
            "operation": "edit_file",
            "path": self.to_relative_path(path),
            "bytes_written": len(updated.encode("utf-8", errors="ignore")),
        }

    def delete_file(self, raw_path: str) -> dict[str, object]:
        path = self.resolve_path(raw_path)
        if not path.exists():
            return {
                "success": False,
                "operation": "delete_file",
                "path": self.to_relative_path(path),
                "error": "Path does not exist",
            }

        if path.is_dir():
            return {
                "success": False,
                "operation": "delete_file",
                "path": self.to_relative_path(path),
                "error": "delete_file only supports files",
            }

        path.unlink()
        return {
            "success": True,
            "operation": "delete_file",
            "path": self.to_relative_path(path),
        }

    def rename_file(self, old_path: str, new_path: str) -> dict[str, object]:
        source = self.resolve_path(old_path)
        target = self.resolve_path(new_path)

        if not source.exists():
            return {
                "success": False,
                "operation": "rename_file",
                "path": self.to_relative_path(source),
                "error": "Source path does not exist",
            }

        target.parent.mkdir(parents=True, exist_ok=True)
        source.rename(target)
        return {
            "success": True,
            "operation": "rename_file",
            "path": self.to_relative_path(source),
            "new_path": self.to_relative_path(target),
        }

    def search_files(self, pattern: str, root: str = ".") -> dict[str, object]:
        search_root = self.resolve_path(root)
        if not search_root.is_dir():
            return {
                "success": False,
                "operation": "search_files",
                "path": self.to_relative_path(search_root),
                "error": "Search root must be a directory",
            }

        matches: list[str] = []
        for path in search_root.rglob("*"):
            if not path.is_file():
                continue
            rel = self.to_relative_path(path)
            if fnmatch(path.name, pattern) or fnmatch(rel, pattern):
                matches.append(rel)

        return {
            "success": True,
            "operation": "search_files",
            "pattern": pattern,
            "matches": sorted(matches),
            "count": len(matches),
        }

    def search_text(
        self,
        query: str,
        root: str = ".",
        is_regex: bool = False,
        max_results: int = 200,
    ) -> dict[str, object]:
        search_root = self.resolve_path(root)
        if not search_root.is_dir():
            return {
                "success": False,
                "operation": "search_text",
                "path": self.to_relative_path(search_root),
                "error": "Search root must be a directory",
            }

        pattern = re.compile(query, re.IGNORECASE) if is_regex else None
        results: list[dict[str, object]] = []

        for path in search_root.rglob("*"):
            if len(results) >= max_results:
                break
            if not path.is_file():
                continue
            if any(part in {".git", ".venv", "__pycache__", "node_modules", ".agent_state", ".agent_logs"} for part in path.parts):
                continue

            text = path.read_text(encoding="utf-8", errors="ignore")
            lines = text.splitlines()
            for index, line in enumerate(lines, start=1):
                matched = bool(pattern.search(line)) if pattern else (query.lower() in line.lower())
                if not matched:
                    continue
                results.append(
                    {
                        "path": self.to_relative_path(path),
                        "line": index,
                        "snippet": line.strip(),
                    }
                )
                if len(results) >= max_results:
                    break

        return {
            "success": True,
            "operation": "search_text",
            "query": query,
            "is_regex": is_regex,
            "matches": results,
            "count": len(results),
        }

    def project_structure(self, root: str = ".", max_items: int = 300) -> dict[str, object]:
        base = self.resolve_path(root)
        if not base.is_dir():
            return {
                "success": False,
                "operation": "project_structure",
                "path": self.to_relative_path(base),
                "error": "Root must be a directory",
            }

        entries: list[dict[str, object]] = []
        for path in sorted(base.rglob("*"), key=lambda item: str(item).lower()):
            if len(entries) >= max_items:
                break
            if any(part in {".git", ".venv", "__pycache__", "node_modules", ".agent_state", ".agent_logs"} for part in path.parts):
                continue
            entries.append(
                {
                    "path": self.to_relative_path(path),
                    "type": "dir" if path.is_dir() else "file",
                }
            )

        return {
            "success": True,
            "operation": "project_structure",
            "path": self.to_relative_path(base),
            "entries": entries,
            "count": len(entries),
        }

    def to_relative_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.workspace_root)).replace("\\", "/") or "."
        except ValueError:
            return str(path)

    def _is_within_workspace(self, path: Path) -> bool:
        try:
            path.relative_to(self.workspace_root)
            return True
        except ValueError:
            return False
