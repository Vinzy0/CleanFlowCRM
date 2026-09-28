from app.db import normalize_database_url


def test_managed_postgres_urls_use_installed_driver():
    for scheme in ("postgres://", "postgresql://"):
        url = f"{scheme}user:pass@host/db?sslmode=require"
        assert normalize_database_url(url) == "postgresql+psycopg://user:pass@host/db?sslmode=require"
    assert normalize_database_url("postgresql+psycopg://user:pass@host/db") == "postgresql+psycopg://user:pass@host/db"
    assert normalize_database_url("sqlite:///local.db") == "sqlite:///local.db"
