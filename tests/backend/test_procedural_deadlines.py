from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace


def fake_request(path: str, method: str) -> SimpleNamespace:
    return SimpleNamespace(url=SimpleNamespace(path=path), method=method)


def create_expediente_with_track(app_bundle: dict[str, object], user: object) -> object:
    routes = app_bundle["expediente_routes"]
    schemas = __import__("backend.app.schemas.expedientes", fromlist=["ExpedienteCreate"])
    session = app_bundle["db"].SessionLocal()
    try:
        payload = schemas.ExpedienteCreate(
            expediente_number="EXP-CNPCF-001",
            title="Juicio civil con pista procesal",
            matter_type="civil",
            jurisdiction_level="federal",
            summary="Expediente con automatizacion de plazos",
            extra={"procedure_track": "mx_cnpcf_base"},
            parties=[{"role": "actor", "display_name": "Parte actora"}],
        )
        return routes.create_expediente(
            payload=payload,
            request=fake_request("/api/v1/expedientes", "POST"),
            current_user=user,
            db=session,
        )
    finally:
        session.close()


def create_document(app_bundle: dict[str, object], user: object, expediente_id: str, document_type: str, title: str) -> object:
    routes = app_bundle["expediente_routes"]
    schemas = __import__("backend.app.schemas.expedientes", fromlist=["DocumentWithVersionCreate"])
    session = app_bundle["db"].SessionLocal()
    try:
        payload = schemas.DocumentWithVersionCreate(
            document={
                "document_type": document_type,
                "title": title,
                "status": "active",
                "event_date": "2026-04-08",
            },
            version={
                "source_kind": "uploaded",
                "file_name": f"{title}.txt",
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


def test_notification_event_auto_generates_procedural_deadline(app_bundle: dict[str, object], make_user) -> None:
    operator = make_user(
        email="operator@example.com",
        display_name="Operator",
        role=app_bundle["enums"].UserRole.OPERATOR,
    )
    expediente = create_expediente_with_track(app_bundle, operator["user"])
    document = create_document(app_bundle, operator["user"], str(expediente.id), "emplazamiento", "Emplazamiento")
    schemas = __import__("backend.app.schemas.expedientes", fromlist=["EventCreate"])
    session = app_bundle["db"].SessionLocal()
    try:
        result = app_bundle["expediente_routes"].create_event(
            expediente_id=str(expediente.id),
            payload=schemas.EventCreate(
                event_type="notificacion",
                title="Notificacion de emplazamiento",
                event_date=datetime(2026, 4, 8, 15, 0, tzinfo=timezone.utc),
                description="Se notifica el emplazamiento",
                document_id=document.id,
            ),
            request=fake_request(f"/api/v1/expedientes/{expediente.id}/events", "POST"),
            current_user=operator["user"],
            db=session,
        )
    finally:
        session.close()

    assert result.event.title == "Notificacion de emplazamiento"
    assert len(result.created_deadlines) == 1
    assert len(result.matched_rules) == 1
    assert result.matched_rules[0].rule_id == "cnpcf_emplazamiento_contestacion_demanda"
    assert result.created_deadlines[0].label == "Vence contestacion de demanda"
    assert result.created_deadlines[0].extra["requires_review"] is True
    assert result.created_deadlines[0].due_at.isoformat().startswith("2026-04-29T15:00:00")


def test_calendar_agenda_aggregates_deadlines_and_audiencias(app_bundle: dict[str, object], make_user) -> None:
    operator = make_user(
        email="operator@example.com",
        display_name="Operator",
        role=app_bundle["enums"].UserRole.OPERATOR,
    )
    expediente = create_expediente_with_track(app_bundle, operator["user"])
    document = create_document(app_bundle, operator["user"], str(expediente.id), "sentencia", "Sentencia")
    schemas = __import__("backend.app.schemas.expedientes", fromlist=["EventCreate"])
    session = app_bundle["db"].SessionLocal()
    try:
        app_bundle["expediente_routes"].create_event(
            expediente_id=str(expediente.id),
            payload=schemas.EventCreate(
                event_type="notificacion",
                title="Notificacion de sentencia",
                event_date=datetime(2026, 4, 8, 9, 30, tzinfo=timezone.utc),
                description="Sentencia definitiva notificada",
                document_id=document.id,
            ),
            request=fake_request(f"/api/v1/expedientes/{expediente.id}/events", "POST"),
            current_user=operator["user"],
            db=session,
        )
        app_bundle["expediente_routes"].create_event(
            expediente_id=str(expediente.id),
            payload=schemas.EventCreate(
                event_type="audiencia",
                title="Audiencia incidental",
                event_date=datetime(2026, 4, 15, 11, 0, tzinfo=timezone.utc),
                description="Audiencia de seguimiento",
                document_id=None,
            ),
            request=fake_request(f"/api/v1/expedientes/{expediente.id}/events", "POST"),
            current_user=operator["user"],
            db=session,
        )
        agenda = app_bundle["expediente_routes"].get_calendar_agenda(
            days_back=0,
            days_forward=60,
            include_satisfied=False,
            _=operator["user"],
            db=session,
        )
    finally:
        session.close()

    kinds = [item.kind for item in agenda.items]
    titles = [item.title for item in agenda.items]
    assert "deadline" in kinds
    assert "audiencia" in kinds
    assert "Vence apelacion contra sentencia definitiva" in titles
    assert "Audiencia incidental" in titles


def test_tracks_endpoint_lists_configured_catalog(app_bundle: dict[str, object], make_user) -> None:
    observer = make_user(
        email="observer@example.com",
        display_name="Observer",
        role=app_bundle["enums"].UserRole.OBSERVER,
    )
    response = app_bundle["expediente_routes"].list_procedural_deadline_tracks(_=observer["user"])

    assert len(response.items) >= 1
    assert response.items[0].id == "mx_cnpcf_base"
    assert response.items[0].rule_count >= 2
