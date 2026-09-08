import httpx
import pytest


@pytest.fixture(autouse=True)
def isolate_external_services(monkeypatch):
    """Tests must never use runner credentials or make real network calls."""
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    monkeypatch.setenv("AUTO_PUBLISH", "false")

    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected real network request in test")

    monkeypatch.setattr(httpx.Client, "send", forbidden)
