from __future__ import annotations

import importlib
import sys
import os
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture
def app_bundle(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory) -> dict[str, object]:
    db_path = tmp_path / "legalize_mx_test.db"
    storage_root = tmp_path / "storage"
    pg_url = os.getenv("LEGALIZE_MX_TEST_DATABASE_URL")
    cleanup_engine = None
    schema = None
    if pg_url:
        from sqlalchemy import create_engine
        from sqlalchemy.engine import make_url
        from sqlalchemy.schema import CreateSchema

        parsed = make_url(pg_url)
        if parsed.host not in {"127.0.0.1", "localhost"} or parsed.database != "legalize_slice0_test" or parsed.password:
            raise RuntimeError("PostgreSQL tests require the explicit passwordless loopback fixture database")
        cleanup_engine = create_engine(pg_url)
        schema = "slice0_" + uuid.uuid4().hex
        with cleanup_engine.begin() as connection:
            connection.execute(CreateSchema(schema))
        db_url = parsed.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
    else:
        db_url = f"sqlite+pysqlite:///{db_path}"
    monkeypatch.setenv("LEGALIZE_MX_DATABASE_URL", db_url)
    monkeypatch.setenv("LEGALIZE_MX_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("LEGALIZE_MX_ALLOW_SQLITE_FALLBACK", "true")
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    for module_name in list(sys.modules):
        if module_name == "backend" or module_name.startswith("backend."):
            sys.modules.pop(module_name, None)

    app_module = importlib.import_module("backend.app.main")
    db_module = importlib.import_module("backend.app.db")
    models_module = importlib.import_module("backend.app.models")
    enums_module = importlib.import_module("backend.app.models.enums")
    security_module = importlib.import_module("backend.app.security")
    deps_module = importlib.import_module("backend.app.deps")
    auth_routes_module = importlib.import_module("backend.app.api.routes.auth")
    expediente_routes_module = importlib.import_module("backend.app.api.routes.expedientes")
    storage_root.mkdir(parents=True, exist_ok=True)
    models_module.Base.metadata.create_all(bind=db_module.engine)

    yield {
        "app": app_module.app,
        "db": db_module,
        "models": models_module,
        "enums": enums_module,
        "security": security_module,
        "deps": deps_module,
        "auth_routes": auth_routes_module,
        "expediente_routes": expediente_routes_module,
    }
    db_module.engine.dispose()
    if cleanup_engine is not None:
        from sqlalchemy.schema import DropSchema

        with cleanup_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        cleanup_engine.dispose()


@pytest.fixture
def make_user(app_bundle: dict[str, object]) -> Callable[..., dict[str, object]]:
    db_module = app_bundle["db"]
    models_module = app_bundle["models"]
    security_module = app_bundle["security"]

    def _make_user(*, email: str, display_name: str, role: object) -> dict[str, object]:
        session = db_module.SessionLocal()
        try:
            user = models_module.AppUser(
                email=email,
                display_name=display_name,
                role=role,
                is_active=True,
            )
            session.add(user)
            session.flush()
            plaintext_api_key, key_prefix, secret_hash = security_module.generate_api_key()
            api_key = models_module.ApiKey(
                user_id=user.id,
                label=f"{display_name.lower().replace(' ', '-')}-key",
                key_prefix=key_prefix,
                secret_hash=secret_hash,
                is_active=True,
            )
            session.add(api_key)
            session.commit()
            session.refresh(user)
            session.refresh(api_key)
            return {"user": user, "api_key": api_key, "plaintext_api_key": plaintext_api_key}
        finally:
            session.close()

    return _make_user
