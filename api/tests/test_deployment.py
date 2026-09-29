from app.db import normalize_database_url
from app.main import configure_cors
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_managed_postgres_urls_use_installed_driver():
    for scheme in ("postgres://", "postgresql://"):
        url = f"{scheme}user:pass@host/db?sslmode=require"
        assert normalize_database_url(url) == "postgresql+psycopg://user:pass@host/db?sslmode=require"
    assert normalize_database_url("postgresql+psycopg://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
    assert normalize_database_url("sqlite:///local.db") == "sqlite:///local.db"


def test_health_checks_database(crm):
    assert crm.client.get("/api/health").json() == {"status": "ok"}


def test_cors_allows_only_configured_frontend():
    app = FastAPI()
    configure_cors(app, "https://tavo-web.onrender.com/")
    client = TestClient(app)
    headers = {"Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"}
    allowed = client.options("/api/leads", headers={**headers, "Origin": "https://tavo-web.onrender.com"})
    denied = client.options("/api/leads", headers={**headers, "Origin": "https://other.example"})
    assert allowed.headers["access-control-allow-origin"] == "https://tavo-web.onrender.com"
    assert "access-control-allow-origin" not in denied.headers
