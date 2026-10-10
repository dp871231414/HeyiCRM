"""pytest 共享夹具 · 使用独立 SQLite 库，避免污染开发数据。"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

DB_FILE = Path(tempfile.gettempdir()) / "fleet_dashboard_test.db"
if DB_FILE.exists():
    DB_FILE.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{DB_FILE}"
os.environ["JWT_SECRET"] = "test-secret-key-0123456789"
os.environ["CORS_ORIGINS"] = ""
os.environ.pop("CURRENT_PERIOD", None)
os.environ.pop("DATA_AS_OF", None)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed(db, reset=True)
    yield


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def login(client: TestClient, account: str, password: str = "Demo#2026"):
    resp = client.post("/api/v1/auth/login", json={"account": account, "password": password})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return {"Authorization": f"Bearer {data['access_token']}"}, data


@pytest.fixture(scope="session")
def admin_headers(client):
    headers, _ = login(client, "chenzm")
    return headers


@pytest.fixture(scope="session")
def member_headers(client):
    headers, _ = login(client, "zhengkai")
    return headers


@pytest.fixture(scope="session")
def head_headers(client):
    headers, _ = login(client, "wangjg")
    return headers


@pytest.fixture(scope="session")
def project_headers(client):
    headers, _ = login(client, "liqiang")
    return headers
