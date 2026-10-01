"""Exercise fresh/populated upgrades with SQLite and optional local PostgreSQL."""
import os
from pathlib import Path
import subprocess
import pytest

from sqlalchemy import create_engine, text
from conftest import postgres_schema


def migrate(url, *args):
    import sys
    env = {**os.environ, "DATABASE_URL": url}
    result = subprocess.run([sys.executable, "-m", "alembic", *args],
                            cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def test_fresh_migration_drift_and_roundtrip(tmp_path):
    url = "sqlite:///" + (tmp_path / "fresh.db").as_posix()
    migrate(url, "upgrade", "head")
    assert "No new upgrade operations" in migrate(url, "check")
    migrate(url, "downgrade", "0003_demo_user_isolation")
    migrate(url, "upgrade", "head")
    migrate(url, "check")


def test_populated_upgrade_preserves_leads_and_backfills_tags(tmp_path):
    url = "sqlite:///" + (tmp_path / "existing.db").as_posix()
    migrate(url, "upgrade", "0003_demo_user_isolation")
    engine = create_engine(url)
    with engine.begin() as db:
        db.execute(text("""INSERT INTO leads
            (inquiry_key, inquiry_fingerprint, name, email, phone, service_type, property_type,
             preferred_date, message, pipeline_stage, is_demo, created_at, updated_at)
            VALUES ('existing-lead', 'fingerprint', 'Synthetic customer', 'customer@example.com',
                    '555-0100', 'Deep Cleaning', 'House', '2026-10-05', 'Existing synthetic request',
                    'New', 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"""))
    migrate(url, "upgrade", "head")
    with engine.connect() as db:
        row = db.execute(text("SELECT name, tags, source FROM leads")).one()
        assert row.name == "Synthetic customer" and row.tags == "[]" and row.source is None
    migrate(url, "check")
    engine.dispose()


@pytest.mark.skipif(not os.getenv("TAVO_TEST_POSTGRES_URL"), reason="Optional local PostgreSQL runtime")
def test_postgres_fresh_populated_upgrade_drift_and_roundtrip():
    with postgres_schema() as isolated:
        url = isolated.render_as_string(hide_password=False)
        migrate(url, "upgrade", "head")
        assert "No new upgrade operations" in migrate(url, "check")
        migrate(url, "downgrade", "0003_demo_user_isolation")
        engine = create_engine(isolated)
        try:
            with engine.begin() as db:
                db.execute(text("""INSERT INTO leads
                    (inquiry_key, inquiry_fingerprint, name, email, phone, service_type, property_type,
                     preferred_date, message, pipeline_stage, is_demo, created_at, updated_at)
                    VALUES ('postgres-existing', 'fingerprint', 'Synthetic customer', 'customer@example.com',
                            '555-0100', 'Deep Cleaning', 'House', '2026-10-05', 'Synthetic PostgreSQL request',
                            'New', false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"""))
            migrate(url, "upgrade", "head")
            assert "No new upgrade operations" in migrate(url, "check")
            with engine.connect() as db:
                row = db.execute(text("SELECT name, tags, source FROM leads")).one()
                assert row.name == "Synthetic customer" and row.tags == [] and row.source is None
        finally:
            engine.dispose()
