from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


@dataclass
class ApprovalRequest:
    request_id: str
    action: str
    details: str
    approved: bool
    token: str
    expires_at: str
    created_at: str


class ApprovalTokenManager:
    def __init__(self, state_dir: Path, ttl_minutes: int = 20) -> None:
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.file_path = self.state_dir / "approval_tokens.json"
        self.ttl_minutes = ttl_minutes

    def request(self, action: str, details: str = "") -> dict[str, Any]:
        payload = self._load()
        now = datetime.now(timezone.utc)
        request_id = secrets.token_hex(6)
        token = secrets.token_urlsafe(24)
        expires = now + timedelta(minutes=self.ttl_minutes)

        payload[request_id] = {
            "request_id": request_id,
            "action": action,
            "details": details,
            "approved": False,
            "token": token,
            "expires_at": expires.isoformat(),
            "created_at": now.isoformat(),
            "used": False,
        }
        self._save(payload)
        return {
            "success": True,
            "request_id": request_id,
            "action": action,
            "details": details,
            "expires_at": expires.isoformat(),
            "approved": False,
        }

    def approve(self, request_id: str) -> dict[str, Any]:
        payload = self._load()
        item = payload.get(request_id)
        if not item:
            return {"success": False, "error": "Approval request not found"}
        if self._is_expired(item.get("expires_at", "")):
            return {"success": False, "error": "Approval request expired"}

        item["approved"] = True
        payload[request_id] = item
        self._save(payload)
        return {
            "success": True,
            "request_id": request_id,
            "approval_token": item.get("token", ""),
            "action": item.get("action", ""),
            "expires_at": item.get("expires_at", ""),
        }

    def validate(self, token: str, action: str) -> bool:
        if not token:
            return False
        payload = self._load()
        for item in payload.values():
            if str(item.get("token", "")) != token:
                continue
            if str(item.get("action", "")) != action:
                continue
            if not bool(item.get("approved", False)):
                continue
            if bool(item.get("used", False)):
                continue
            if self._is_expired(str(item.get("expires_at", ""))):
                continue
            return True
        return False

    def consume(self, token: str, action: str) -> bool:
        payload = self._load()
        for key, item in payload.items():
            if str(item.get("token", "")) != token:
                continue
            if str(item.get("action", "")) != action:
                continue
            if not bool(item.get("approved", False)):
                continue
            if bool(item.get("used", False)):
                continue
            if self._is_expired(str(item.get("expires_at", ""))):
                continue
            item["used"] = True
            payload[key] = item
            self._save(payload)
            return True
        return False

    def list_requests(self) -> dict[str, Any]:
        payload = self._load()
        rows: list[dict[str, Any]] = []
        for item in payload.values():
            rows.append(
                {
                    "request_id": item.get("request_id", ""),
                    "action": item.get("action", ""),
                    "details": item.get("details", ""),
                    "approved": bool(item.get("approved", False)),
                    "used": bool(item.get("used", False)),
                    "expired": self._is_expired(str(item.get("expires_at", ""))),
                    "created_at": item.get("created_at", ""),
                    "expires_at": item.get("expires_at", ""),
                }
            )
        rows.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
        return {"success": True, "requests": rows}

    def _is_expired(self, iso_value: str) -> bool:
        try:
            expiry = datetime.fromisoformat(iso_value)
        except ValueError:
            return True
        return datetime.now(timezone.utc) >= expiry

    def _load(self) -> dict[str, dict[str, Any]]:
        if not self.file_path.exists():
            return {}
        try:
            data = json.loads(self.file_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            return {}
        return {}

    def _save(self, payload: dict[str, dict[str, Any]]) -> None:
        self.file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
