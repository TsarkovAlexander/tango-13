from app.tracing import redact


def test_redacts_secret_keys_and_values() -> None:
    payload = {
        "tenant_id": "tenant-a",
        "api_key": "plain-secret",
        "nested": {
            "message": "use sk-abcdefghijklmnopqrstuvwxyz123456",
            "safe": "value",
        },
    }

    assert redact(payload) == {
        "tenant_id": "tenant-a",
        "api_key": "[redacted]",
        "nested": {
            "message": "use [redacted]",
            "safe": "value",
        },
    }
