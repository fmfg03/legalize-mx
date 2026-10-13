from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


def fake_request(path: str, method: str) -> SimpleNamespace:
    return SimpleNamespace(url=SimpleNamespace(path=path), method=method)


def create_sample_expediente(app_bundle: dict[str, object], user: object) -> object:
    routes = app_bundle["expediente_routes"]
    schemas = __import__("backend.app.schemas.expedientes", fromlist=["ExpedienteCreate"])
    session = app_bundle["db"].SessionLocal()
    try:
        payload = schemas.ExpedienteCreate(
            expediente_number="EXP-TEST-001",
            title="Expediente de prueba",
            matter_type="amparo",
            jurisdiction_level="federal",
            summary="Caso de prueba",
            parties=[{"role": "quejoso", "display_name": "Persona Prueba"}],
        )
        return routes.create_expediente(
            payload=payload,
            request=fake_request("/api/v1/expedientes", "POST"),
            current_user=user,
            db=session,
        )
    finally:
        session.close()


def create_sample_document(app_bundle: dict[str, object], user: object, expediente_id: str) -> object:
    routes = app_bundle["expediente_routes"]
    schemas = __import__("backend.app.schemas.expedientes", fromlist=["DocumentWithVersionCreate"])
    session = app_bundle["db"].SessionLocal()
    try:
        payload = schemas.DocumentWithVersionCreate(
            document={
                "document_type": "acuerdo",
                "title": "Acuerdo de prueba",
                "status": "active",
                "event_date": "2026-04-05",
            },
            version={
                "source_kind": "generated",
                "file_name": "acuerdo-prueba.txt",
                "mime_type": "text/plain",
                "content_base64": "RG9jdW1lbnRvIGRlIHBydWViYS4=",
            },
        )
        detail = routes.create_document(
            expediente_id=expediente_id,
            payload=payload,
            request=fake_request(f"/api/v1/expedientes/{expediente_id}/documents", "POST"),
            current_user=user,
            db=session,
        )
        return detail.documents[0]
    finally:
        session.close()


def test_get_current_user_resolves_valid_api_key(app_bundle: dict[str, object], make_user) -> None:
    actor = make_user(
        email="admin@example.com",
        display_name="Admin",
        role=app_bundle["enums"].UserRole.ADMIN,
    )
    session = app_bundle["db"].SessionLocal()
    try:
        current_user = app_bundle["deps"].get_current_user(
            authorization=f"Bearer {actor['plaintext_api_key']}",
            x_api_key=None,
            db=session,
        )
    finally:
        session.close()

    assert current_user.email == "admin@example.com"
    assert current_user.role == app_bundle["enums"].UserRole.ADMIN


def test_get_current_user_rejects_missing_api_key(app_bundle: dict[str, object]) -> None:
    session = app_bundle["db"].SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            app_bundle["deps"].get_current_user(authorization=None, x_api_key=None, db=session)
    finally:
        session.close()

    assert exc_info.value.status_code == 401


def test_role_guards_enforce_read_write_review_boundaries(app_bundle: dict[str, object], make_user) -> None:
    enums = app_bundle["enums"]
    deps = app_bundle["deps"]
    observer = make_user(email="observer@example.com", display_name="Observer", role=enums.UserRole.OBSERVER)
    operator = make_user(email="operator@example.com", display_name="Operator", role=enums.UserRole.OPERATOR)
    reviewer = make_user(email="reviewer@example.com", display_name="Reviewer", role=enums.UserRole.REVIEWER)

    assert deps.require_read_user(observer["user"]).role == enums.UserRole.OBSERVER
    assert deps.require_operator_user(operator["user"]).role == enums.UserRole.OPERATOR
    assert deps.require_reviewer_user(reviewer["user"]).role == enums.UserRole.REVIEWER

    with pytest.raises(HTTPException) as observer_exc:
        deps.require_operator_user(observer["user"])
    with pytest.raises(HTTPException) as operator_exc:
        deps.require_admin_user(operator["user"])
    with pytest.raises(HTTPException) as operator_review_exc:
        deps.require_reviewer_user(operator["user"])

    assert observer_exc.value.status_code == 403
    assert operator_exc.value.status_code == 403
    assert operator_review_exc.value.status_code == 403


def test_create_expediente_sets_actor_and_persists_audit_log(app_bundle: dict[str, object], make_user) -> None:
    operator = make_user(
        email="operator@example.com",
        display_name="Operator",
        role=app_bundle["enums"].UserRole.OPERATOR,
    )
    expediente = create_sample_expediente(app_bundle, operator["user"])

    session = app_bundle["db"].SessionLocal()
    try:
        audit_response = app_bundle["expediente_routes"].list_audit_logs(
            expediente_id=str(expediente.id),
            action="create_expediente",
            entity_type=None,
            actor_user_id=str(operator["user"].id),
            limit=10,
            _=operator["user"],
            db=session,
        )
    finally:
        session.close()

    assert str(expediente.created_by_user_id) == str(operator["user"].id)
    assert str(expediente.updated_by_user_id) == str(operator["user"].id)
    assert len(audit_response.items) == 1
    assert str(audit_response.items[0].actor_user_id) == str(operator["user"].id)
    assert audit_response.items[0].action == "create_expediente"


def test_create_release_receipt_tracks_reviewer_actor(app_bundle: dict[str, object], make_user) -> None:
    admin = make_user(email="admin@example.com", display_name="Admin", role=app_bundle["enums"].UserRole.ADMIN)
    reviewer = make_user(
        email="reviewer@example.com",
        display_name="Reviewer",
        role=app_bundle["enums"].UserRole.REVIEWER,
    )
    expediente = create_sample_expediente(app_bundle, admin["user"])
    document = create_sample_document(app_bundle, admin["user"], str(expediente.id))
    version_id = str(document.versions[0].id)
    schemas = __import__("backend.app.schemas.expedientes", fromlist=["ReleaseReceiptCreate"])
    session = app_bundle["db"].SessionLocal()
    try:
        content = __import__("backend.app.storage", fromlist=["resolve_storage_path"]).resolve_storage_path(document.versions[0].storage_key).read_text()
        bundle = {"response_text": content, "response_type": "recommendation", "citations": [], "claims": []}
        execution = app_bundle["expediente_routes"].create_release_evaluation(
            expediente_id=str(expediente.id),
            payload=schemas.ReleaseEvaluationCreate(document_version_id=version_id, bundle=bundle),
            current_user=reviewer["user"], db=session,
        )
        receipt = app_bundle["expediente_routes"].create_release_receipt(
            expediente_id=str(expediente.id),
            payload=schemas.ReleaseReceiptCreate(execution_id=execution.id, bundle=bundle),
            request=fake_request(f"/api/v1/expedientes/{expediente.id}/release-receipts", "POST"),
            current_user=reviewer["user"],
            db=session,
        )
    finally:
        session.close()

    assert str(receipt.created_by_user_id) == str(reviewer["user"].id)


def test_admin_route_creates_user_and_api_key_with_audit(app_bundle: dict[str, object], make_user) -> None:
    admin = make_user(email="admin@example.com", display_name="Admin", role=app_bundle["enums"].UserRole.ADMIN)
    auth_routes = app_bundle["auth_routes"]
    schemas = __import__("backend.app.schemas.auth", fromlist=["UserCreate", "ApiKeyCreate"])
    session = app_bundle["db"].SessionLocal()
    try:
        created_user = auth_routes.create_user(
            payload=schemas.UserCreate(email="new.user@example.com", display_name="New User", role="operator"),
            request=fake_request("/api/v1/admin/users", "POST"),
            admin_user=admin["user"],
            db=session,
        )
        api_key = auth_routes.create_api_key(
            user_id=str(created_user.id),
            payload=schemas.ApiKeyCreate(label="new-user-key"),
                request=fake_request(f"/api/v1/admin/users/{created_user.id}/api-keys", "POST"),
                admin_user=admin["user"],
                db=session,
            )
        created_user_email = created_user.email
        plaintext_api_key = api_key.plaintext_api_key
    finally:
        session.close()

    assert created_user_email == "new.user@example.com"
    assert plaintext_api_key.startswith("lmx_")


def test_admin_can_update_user_and_deactivated_user_cannot_authenticate(
    app_bundle: dict[str, object], make_user
) -> None:
    admin = make_user(email="admin@example.com", display_name="Admin", role=app_bundle["enums"].UserRole.ADMIN)
    operator = make_user(
        email="operator@example.com",
        display_name="Operator",
        role=app_bundle["enums"].UserRole.OPERATOR,
    )
    auth_routes = app_bundle["auth_routes"]
    schemas = __import__("backend.app.schemas.auth", fromlist=["UserUpdate"])
    session = app_bundle["db"].SessionLocal()
    try:
        updated_user = auth_routes.update_user(
            user_id=str(operator["user"].id),
            payload=schemas.UserUpdate(display_name="Operador MX", is_active=False),
            request=fake_request(f"/api/v1/admin/users/{operator['user'].id}", "PATCH"),
            admin_user=admin["user"],
            db=session,
        )
    finally:
        session.close()

    assert updated_user.display_name == "Operador MX"
    assert updated_user.is_active is False

    auth_session = app_bundle["db"].SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            app_bundle["deps"].get_current_user(
                authorization=f"Bearer {operator['plaintext_api_key']}",
                x_api_key=None,
                db=auth_session,
            )
    finally:
        auth_session.close()

    assert exc_info.value.status_code == 403


def test_admin_can_list_and_deactivate_api_keys(app_bundle: dict[str, object], make_user) -> None:
    admin = make_user(email="admin@example.com", display_name="Admin", role=app_bundle["enums"].UserRole.ADMIN)
    operator = make_user(
        email="operator@example.com",
        display_name="Operator",
        role=app_bundle["enums"].UserRole.OPERATOR,
    )
    auth_routes = app_bundle["auth_routes"]
    schemas = __import__("backend.app.schemas.auth", fromlist=["ApiKeyCreate", "ApiKeyUpdate"])
    session = app_bundle["db"].SessionLocal()
    try:
        created_key = auth_routes.create_api_key(
            user_id=str(operator["user"].id),
            payload=schemas.ApiKeyCreate(label="secondary-key"),
            request=fake_request(f"/api/v1/admin/users/{operator['user'].id}/api-keys", "POST"),
            admin_user=admin["user"],
            db=session,
        )
        key_list = auth_routes.list_api_keys(
            user_id=str(operator["user"].id),
            _=admin["user"],
            db=session,
        )
        updated_key = auth_routes.update_api_key(
            user_id=str(operator["user"].id),
            api_key_id=str(created_key.id),
            payload=schemas.ApiKeyUpdate(is_active=False),
            request=fake_request(f"/api/v1/admin/users/{operator['user'].id}/api-keys/{created_key.id}", "PATCH"),
            admin_user=admin["user"],
            db=session,
        )
    finally:
        session.close()

    assert len(key_list.items) == 2
    assert {item.label for item in key_list.items} == {"operator-key", "secondary-key"}
    assert updated_key.is_active is False

    auth_session = app_bundle["db"].SessionLocal()
    try:
        with pytest.raises(HTTPException) as exc_info:
            app_bundle["deps"].get_current_user(
                authorization=f"Bearer {created_key.plaintext_api_key}",
                x_api_key=None,
                db=auth_session,
            )
    finally:
        auth_session.close()

    assert exc_info.value.status_code == 401


def test_admin_global_audit_log_filters_include_actor_action_and_time(
    app_bundle: dict[str, object], make_user
) -> None:
    admin = make_user(email="admin@example.com", display_name="Admin", role=app_bundle["enums"].UserRole.ADMIN)
    operator = make_user(
        email="operator@example.com",
        display_name="Operator",
        role=app_bundle["enums"].UserRole.OPERATOR,
    )
    auth_routes = app_bundle["auth_routes"]
    schemas = __import__("backend.app.schemas.auth", fromlist=["UserCreate", "UserUpdate"])
    before_actions = datetime.now(timezone.utc) - timedelta(minutes=1)
    session = app_bundle["db"].SessionLocal()
    try:
        created_user = auth_routes.create_user(
            payload=schemas.UserCreate(email="audit.user@example.com", display_name="Audit User", role="observer"),
            request=fake_request("/api/v1/admin/users", "POST"),
            admin_user=admin["user"],
            db=session,
        )
        auth_routes.update_user(
            user_id=str(created_user.id),
            payload=schemas.UserUpdate(is_active=False),
            request=fake_request(f"/api/v1/admin/users/{created_user.id}", "PATCH"),
            admin_user=admin["user"],
            db=session,
        )
        filtered_logs = auth_routes.list_audit_logs(
            actor_user_id=str(admin["user"].id),
            action="update_user",
            entity_type="app_user",
            expediente_id=None,
            entity_id=str(created_user.id),
            created_from=before_actions,
            created_to=datetime.now(timezone.utc) + timedelta(minutes=1),
            limit=20,
            _=admin["user"],
            db=session,
        )
    finally:
        session.close()

    assert len(filtered_logs.items) == 1
    assert filtered_logs.items[0].action == "update_user"
    assert str(filtered_logs.items[0].actor_user_id) == str(admin["user"].id)
    assert str(filtered_logs.items[0].entity_id) == str(created_user.id)
