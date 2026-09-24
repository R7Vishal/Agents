from pathlib import Path

from coding_agent.integrity import (
    get_active_signing_key,
    load_or_create_hmac_keyring,
    rotate_hmac_key,
    verify_checkpoint_payload,
    wrap_checkpoint_payload,
)


def test_key_rotation_keeps_old_checkpoint_verifiable(tmp_path: Path) -> None:
    keyring = load_or_create_hmac_keyring(tmp_path)
    key_id_1, key_1 = get_active_signing_key(keyring)

    payload = {"T1": {"status": "COMPLETED"}}
    envelope_old = wrap_checkpoint_payload(payload, key=key_1, key_id=key_id_1, signature_version="v2")
    assert verify_checkpoint_payload(envelope_old, keyring=keyring)

    rotation = rotate_hmac_key(tmp_path)
    assert rotation["new_key_id"] != key_id_1

    keyring_rotated = load_or_create_hmac_keyring(tmp_path)
    assert verify_checkpoint_payload(envelope_old, keyring=keyring_rotated)

    key_id_2, key_2 = get_active_signing_key(keyring_rotated)
    envelope_new = wrap_checkpoint_payload(payload, key=key_2, key_id=key_id_2, signature_version="v2")
    assert verify_checkpoint_payload(envelope_new, keyring=keyring_rotated)


def test_backward_compatible_v1_signature_without_key_id(tmp_path: Path) -> None:
    keyring = load_or_create_hmac_keyring(tmp_path)
    key_id, key = get_active_signing_key(keyring)

    payload = {"T2": {"status": "FAILED"}}
    envelope_v1 = wrap_checkpoint_payload(payload, key=key, key_id=key_id, signature_version="v1")
    assert "key_id" not in envelope_v1
    assert verify_checkpoint_payload(envelope_v1, keyring=keyring)
