import time

from app.services.webhooks import sign_payload, verify_signature


def test_valid_signature_round_trips():
    secret = "test-secret"
    body = b'{"event":"task.created"}'
    header = sign_payload(secret, body, timestamp=int(time.time()))
    assert verify_signature(secret, body, header)


def test_tampered_body_fails_verification():
    secret = "test-secret"
    header = sign_payload(secret, b'{"event":"task.created"}', timestamp=int(time.time()))
    assert not verify_signature(secret, b'{"event":"task.deleted"}', header)


def test_stale_timestamp_rejected_as_replay():
    secret = "test-secret"
    body = b"{}"
    header = sign_payload(secret, body, timestamp=1)  # far in the past
    assert not verify_signature(secret, body, header)
