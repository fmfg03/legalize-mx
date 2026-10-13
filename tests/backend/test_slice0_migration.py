from __future__ import annotations

import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile


def test_migration_from_main_schema_preserves_legacy_receipts(tmp_path):
    root = Path(__file__).parents[2]
    old = tmp_path / "main"
    old.mkdir()
    legacy_revision = "a1c226260019c0da40d45eff2d1fa5dd42b40ce4"
    archive = subprocess.run(["git", "archive", legacy_revision, "backend"], cwd=root, capture_output=True, check=True).stdout
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(old, filter="data")
    db_url = f"sqlite+pysqlite:///{tmp_path / 'migration.sqlite'}"
    env = {**os.environ, "LEGALIZE_MX_DATABASE_URL": db_url, "LEGALIZE_MX_MCP_ENABLED": "false"}
    code = '''
from backend.app.models import Base, ReleaseReceipt, AppUser
from backend.app.models.enums import ReleaseVerdict, UserRole
from backend.app.db import engine, SessionLocal
Base.metadata.create_all(engine)
with SessionLocal() as db:
    db.add(AppUser(email="legacy@example.test", display_name="Legacy", role=UserRole.REVIEWER, is_active=True))
    db.add(ReleaseReceipt(verdict=ReleaseVerdict.APPROVED, gate_summary={"legacy": True}))
    db.commit()
'''
    subprocess.run([sys.executable, "-c", code], cwd=old, env=env, capture_output=True, check=True)
    for action in (["stamp", "20260405_0002"], ["upgrade", "head"], ["check"]):
        result = subprocess.run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", *action], cwd=root, env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    code = '''
from sqlalchemy import select, func
from backend.app.models import ReleaseReceipt, OAuthBinding, GateExecution, ReleaseOutbox
from backend.app.db import SessionLocal
with SessionLocal() as db:
    receipt = db.scalar(select(ReleaseReceipt))
    assert receipt.execution_id is None
    assert receipt.gate_summary == {"legacy": True}
    for model in (OAuthBinding, GateExecution, ReleaseOutbox):
        assert db.scalar(select(func.count()).select_from(model)) == 0
'''
    subprocess.run([sys.executable, "-c", code], cwd=root, env=env, capture_output=True, check=True)
    result = subprocess.run([sys.executable, "-m", "alembic", "-c", "backend/alembic.ini", "downgrade", "20260405_0002"], cwd=root, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    read_old = '''
from sqlalchemy import select
from backend.app.models import ReleaseReceipt, AppUser
from backend.app.db import SessionLocal
with SessionLocal() as db:
    assert db.scalar(select(ReleaseReceipt)).verdict.value == "approved"
    assert db.scalar(select(AppUser)).role.value == "reviewer"
'''
    subprocess.run([sys.executable, "-c", read_old], cwd=old, env=env, capture_output=True, check=True)
