"""Redaction (B3): secrets are scrubbed before evidence leaves the cluster."""

from app.aiops.redact import redact


def test_redacts_bearer_and_provider_tokens():
    assert "abc.def.ghi" not in redact("Authorization: Bearer abc.def.ghi")
    assert "REDACTED_TOKEN" in redact("env GROQ_KEY=gsk_1234567890abcdef set")
    assert "REDACTED_AWS_KEY" in redact("creds AKIAIOSFODNN7EXAMPLE loaded")


def test_redacts_connection_string_password():
    out = redact("postgresql://aiops:s3cr3tpw@postgres:5432/aiops")
    assert "s3cr3tpw" not in out
    assert "[REDACTED]" in out


def test_redacts_kv_secret_and_email():
    assert "hunter2" not in redact('config password="hunter2"')
    assert "REDACTED_EMAIL" in redact("user alice@example.com logged in")


def test_keeps_ordinary_text_and_ips():
    out = redact("scored 12000 flows from 192.168.1.5 p95 6ms")
    assert "192.168.1.5" in out      # IPs are operationally relevant — kept
    assert "12000 flows" in out
