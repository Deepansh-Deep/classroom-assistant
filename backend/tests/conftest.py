import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-that-is-long-enough-1234567890")
    monkeypatch.setenv("GROQ_API_KEY", "")
    monkeypatch.setenv("FRONTEND_DIR", str(tmp_path / "nofrontend"))
    from classroom import config
    config.get_settings.cache_clear()
    import importlib
    import classroom.security as sec
    sec._fernet.cache_clear()
    import classroom.api as api
    importlib.reload(api)
    from fastapi.testclient import TestClient
    with TestClient(api.app) as c:
        yield c
    config.get_settings.cache_clear()


def login(client, role):
    tok = client.post("/api/auth/demo", json={"role": role}).json()["token"]
    return {"Authorization": f"Bearer {tok}"}
