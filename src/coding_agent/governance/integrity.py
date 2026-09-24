from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from pathlib import Path
from typing import Any


HMAC_KEY_FILE = ".checkpoint_hmac_key"
HMAC_KEYRING_FILE = ".checkpoint_hmac_keyring.json"


def compute_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _default_keyring() -> dict[str, Any]:
    key_id = "k1"
    return {
        "version": 1,
        "active_key_id": key_id,
        "keys": {
            key_id: secrets.token_hex(32),
        },
    }


def _save_keyring(path: Path, keyring: dict[str, Any]) -> None:
    path.write_text(json.dumps(keyring, indent=2), encoding="utf-8")


def load_or_create_hmac_keyring(state_dir: Path) -> dict[str, Any]:
    keyring_file = state_dir / HMAC_KEYRING_FILE

    if keyring_file.exists():
        data = json.loads(keyring_file.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("keys"), dict) and data.get("active_key_id"):
            return data

    legacy_key_file = state_dir / HMAC_KEY_FILE
    if legacy_key_file.exists():
        legacy_key = legacy_key_file.read_text(encoding="utf-8").strip()
        if legacy_key:
            keyring = {
                "version": 1,
                "active_key_id": "k1",
                "keys": {"k1": legacy_key},
            }
            _save_keyring(keyring_file, keyring)
            return keyring

    keyring = _default_keyring()
    _save_keyring(keyring_file, keyring)
    return keyring


def get_active_signing_key(keyring: dict[str, Any]) -> tuple[str, str]:
    active_key_id = str(keyring.get("active_key_id", ""))
    keys = keyring.get("keys", {})
    if not active_key_id or active_key_id not in keys:
        raise ValueError("Invalid keyring: active key missing")
    return active_key_id, str(keys[active_key_id])


def rotate_hmac_key(state_dir: Path) -> dict[str, Any]:
    keyring = load_or_create_hmac_keyring(state_dir)
    keys = dict(keyring.get("keys", {}))

    numeric_ids = []
    for key_id in keys:
        if key_id.startswith("k") and key_id[1:].isdigit():
            numeric_ids.append(int(key_id[1:]))
    next_id = max(numeric_ids, default=0) + 1
    new_key_id = f"k{next_id}"

    keys[new_key_id] = secrets.token_hex(32)
    keyring["keys"] = keys
    keyring["active_key_id"] = new_key_id

    _save_keyring(state_dir / HMAC_KEYRING_FILE, keyring)
    return {
        "new_key_id": new_key_id,
        "total_keys": len(keys),
    }


def _hmac_sign(checkpoint_data: dict[str, Any], key: str) -> str:
    canonical = json.dumps(checkpoint_data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(key.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def wrap_checkpoint_payload(
    checkpoint_data: dict[str, Any],
    key: str,
    key_id: str,
    signature_version: str = "v2",
) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "data": checkpoint_data,
        "algorithm": "HMAC-SHA256",
        "signature_version": signature_version,
        "signature": _hmac_sign(checkpoint_data, key),
    }
    if signature_version == "v2":
        envelope["key_id"] = key_id
    return envelope


def _find_verification_key(
    checkpoint_payload: dict[str, Any],
    keyring: dict[str, Any],
) -> tuple[str, str] | None:
    keys = keyring.get("keys", {})
    if not isinstance(keys, dict):
        return None

    key_id = checkpoint_payload.get("key_id")
    if isinstance(key_id, str) and key_id in keys:
        return key_id, str(keys[key_id])

    signature = checkpoint_payload.get("signature")
    data = checkpoint_payload.get("data")
    if not isinstance(signature, str) or not isinstance(data, dict):
        return None

    for candidate_key_id, candidate_key in keys.items():
        expected = _hmac_sign(data, str(candidate_key))
        if hmac.compare_digest(expected, signature):
            return str(candidate_key_id), str(candidate_key)
    return None


def verify_checkpoint_payload(checkpoint_payload: dict[str, Any], keyring: dict[str, Any]) -> bool:
    data = checkpoint_payload.get("data")
    if not isinstance(data, dict):
        return False

    signature = checkpoint_payload.get("signature")
    if isinstance(signature, str) and signature:
        key_info = _find_verification_key(checkpoint_payload, keyring)
        if not key_info:
            return False
        _, key = key_info
        expected = _hmac_sign(data, key)
        return hmac.compare_digest(expected, signature)

    legacy_hash = checkpoint_payload.get("hash")
    if isinstance(legacy_hash, str) and legacy_hash:
        return compute_hash(data) == legacy_hash

    return False


def checkpoint_forensics(checkpoint_payload: dict[str, Any], keyring: dict[str, Any]) -> dict[str, Any]:
    data = checkpoint_payload.get("data") if isinstance(checkpoint_payload, dict) else None
    expected_signature = checkpoint_payload.get("signature") if isinstance(checkpoint_payload, dict) else None
    expected_hash = checkpoint_payload.get("hash") if isinstance(checkpoint_payload, dict) else None
    algorithm = checkpoint_payload.get("algorithm") if isinstance(checkpoint_payload, dict) else None
    signature_version = checkpoint_payload.get("signature_version") if isinstance(checkpoint_payload, dict) else None
    key_id = checkpoint_payload.get("key_id") if isinstance(checkpoint_payload, dict) else None
    active_key_id = keyring.get("active_key_id") if isinstance(keyring, dict) else None

    resolved_key_id = ""
    resolved_key = ""
    found = _find_verification_key(checkpoint_payload, keyring)
    if found:
        resolved_key_id, resolved_key = found

    details: dict[str, Any] = {
        "envelope_type": "",
        "algorithm": algorithm if isinstance(algorithm, str) else "",
        "signature_version": signature_version if isinstance(signature_version, str) else "",
        "key_id": key_id if isinstance(key_id, str) else "",
        "resolved_key_id": resolved_key_id,
        "active_key_id": active_key_id if isinstance(active_key_id, str) else "",
        "expected_signature": expected_signature if isinstance(expected_signature, str) else "",
        "actual_signature": "",
        "expected_hash": expected_hash if isinstance(expected_hash, str) else "",
        "actual_hash": "",
        "task_ids": [],
        "task_count": 0,
        "payload_keys": [],
    }

    if isinstance(data, dict):
        details["actual_hash"] = compute_hash(data)
        if resolved_key:
            details["actual_signature"] = _hmac_sign(data, resolved_key)
        details["task_ids"] = sorted(list(data.keys()))[:50]
        details["task_count"] = len(data)
        details["payload_keys"] = sorted(list(data.keys()))[:10]

    if isinstance(expected_signature, str) and expected_signature:
        details["envelope_type"] = "hmac"
    elif isinstance(expected_hash, str) and expected_hash:
        details["envelope_type"] = "legacy-hash"
    else:
        details["envelope_type"] = "unknown"

    return details
