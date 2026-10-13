from __future__ import annotations

import os
import json
from pathlib import Path
import subprocess
import sys
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema


@pytest.mark.skipif(not os.getenv("LEGALIZE_MX_TEST_DATABASE_URL"), reason="Requires isolated loopback PostgreSQL fixture")
def test_full_postgres_migration_chain_matches_models_and_preserves_legacy(tmp_path):
    url = make_url(os.environ["LEGALIZE_MX_TEST_DATABASE_URL"])
    assert url.host in {"127.0.0.1", "localhost"} and url.database == "legalize_slice0_test" and not url.password
    engine = create_engine(url)
    schema = "migration_" + uuid.uuid4().hex
    with engine.begin() as connection:
        connection.execute(CreateSchema(schema))
    scoped = url.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    env = {**os.environ, "LEGALIZE_MX_DATABASE_URL": scoped, "LEGALIZE_MX_MCP_ENABLED": "false"}
    root = Path(__file__).parents[2]
    try:
        for action in (["upgrade", "20260405_0002"], ["upgrade", "head"], ["check"]):
            result = subprocess.run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", *action], cwd=root, env=env, capture_output=True, text=True)
            assert result.returncode == 0, result.stdout + result.stderr
            if action == ["upgrade", "20260405_0002"]:
                legacy_engine = create_engine(scoped)
                with legacy_engine.begin() as connection:
                    connection.execute(text("INSERT INTO release_receipts (id,verdict,gate_summary) VALUES (:id,'approved',CAST(:summary AS json))"), {"id": uuid.uuid4(), "summary": json.dumps({"legacy": True})})
                legacy_engine.dispose()
        code = '''
from sqlalchemy import select
from backend.app.db import SessionLocal
from backend.app.models import AppUser, ReleaseReceipt, OAuthBinding
from backend.app.models.enums import UserRole, ReleaseVerdict
with SessionLocal() as db:
    user = AppUser(email="pg@example.test",display_name="PG",role=UserRole.REVIEWER,is_active=True)
    db.add(user)
    db.flush()
    db.commit()
    assert db.scalar(select(AppUser)).role == UserRole.REVIEWER
    assert db.scalar(select(ReleaseReceipt)).execution_id is None
    assert db.scalar(select(ReleaseReceipt)).gate_summary == {"legacy": True}
'''
        subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, check=True)
        result = subprocess.run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "downgrade", "20260405_0002"], cwd=root, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        with engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        engine.dispose()
