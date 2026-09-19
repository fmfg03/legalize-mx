from __future__ import annotations

from http import HTTPStatus
from types import SimpleNamespace

from fastapi.encoders import jsonable_encoder


def fake_request(path: str, method: str) -> SimpleNamespace:
    return SimpleNamespace(url=SimpleNamespace(path=path), method=method)


class FakeHandler:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload
        self.response: dict[str, object] | None = None
        self.status: HTTPStatus | None = None

    def read_json_body(self) -> dict[str, object]:
        return self._payload

    def write_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        self.response = payload
        self.status = status

    def write_error_json(self, detail: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
        self.response = {"error": detail}
        self.status = status


def create_expediente(app_bundle: dict[str, object], user: object) -> object:
    routes = app_bundle["expediente_routes"]
    schemas = __import__("backend.app.schemas.expedientes", fromlist=["ExpedienteCreate"])
    session = app_bundle["db"].SessionLocal()
    try:
        payload = schemas.ExpedienteCreate(
            expediente_number="EXP-FLOW-001",
            title="Expediente flujo completo",
            matter_type="amparo",
            jurisdiction_level="federal",
            court_or_authority="Juzgado de Distrito",
            summary="Expediente para smoke test del workspace",
            parties=[{"role": "quejoso", "display_name": "Persona Flujo"}],
        )
        return routes.create_expediente(
            payload=payload,
            request=fake_request("/api/v1/expedientes", "POST"),
            current_user=user,
            db=session,
        )
    finally:
        session.close()


def create_source_document(app_bundle: dict[str, object], user: object, expediente_id: str) -> object:
    routes = app_bundle["expediente_routes"]
    schemas = __import__("backend.app.schemas.expedientes", fromlist=["DocumentWithVersionCreate"])
    session = app_bundle["db"].SessionLocal()
    try:
        payload = schemas.DocumentWithVersionCreate(
            document={
                "document_type": "demanda",
                "title": "Demanda inicial",
                "description": "Documento base del expediente",
                "status": "active",
                "event_date": "2026-04-10",
            },
            version={
                "source_kind": "uploaded",
                "file_name": "demanda-inicial.txt",
                "mime_type": "text/plain",
                "content_base64": "RGVtYW5kYSBpbmljaWFsIGNvbiBoZWNob3MgeSBwcmV0ZW5zaW9uZXMu",
                "extracted_text": (
                    "Demanda inicial con hechos, acto reclamado y referencias a notificacion y personeria."
                ),
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


def build_backend_dispatch(app_bundle: dict[str, object], user: object):
    routes = app_bundle["expediente_routes"]
    schemas = __import__("backend.app.schemas.expedientes", fromlist=["ExpedienteUpdate"])

    def dispatch(method: str, path: str, *, payload=None):
        session = app_bundle["db"].SessionLocal()
        try:
            if method == "GET" and path.startswith("/expedientes/") and path.endswith("/release-receipts"):
                expediente_id = path.split("/")[2]
                response = routes.list_release_receipts(
                    expediente_id=expediente_id,
                    _=user,
                    db=session,
                )
                return jsonable_encoder(response)
            if method == "GET" and path.startswith("/expedientes/") and "/documents/" in path:
                parts = path.strip("/").split("/")
                expediente_id = parts[1]
                document_id = parts[3]
                response = routes.get_document(
                    expediente_id=expediente_id,
                    document_id=document_id,
                    _=user,
                    db=session,
                )
                return jsonable_encoder(response)
            if method == "GET" and path.startswith("/expedientes/"):
                expediente_id = path.split("/")[2]
                response = routes.get_expediente(expediente_id=expediente_id, _=user, db=session)
                return jsonable_encoder(response)
            if method == "PATCH" and path.startswith("/expedientes/") and path.count("/") == 2:
                expediente_id = path.split("/")[2]
                response = routes.update_expediente(
                    expediente_id=expediente_id,
                    payload=schemas.ExpedienteUpdate(**(payload or {})),
                    request=fake_request(path, "PATCH"),
                    current_user=user,
                    db=session,
                )
                return jsonable_encoder(response)
            if method == "POST" and path.startswith("/expedientes/") and path.endswith("/documents"):
                expediente_id = path.split("/")[2]
                document_payload = schemas.DocumentWithVersionCreate(**(payload or {}))
                response = routes.create_document(
                    expediente_id=expediente_id,
                    payload=document_payload,
                    request=fake_request(path, "POST"),
                    current_user=user,
                    db=session,
                )
                return jsonable_encoder(response)
            if method == "POST" and "/documents/" in path and path.endswith("/versions"):
                parts = path.strip("/").split("/")
                expediente_id = parts[1]
                document_id = parts[3]
                version_payload = schemas.DocumentVersionCreate(**(payload or {}))
                response = routes.create_document_version(
                    expediente_id=expediente_id,
                    document_id=document_id,
                    payload=version_payload,
                    request=fake_request(path, "POST"),
                    current_user=user,
                    db=session,
                )
                return jsonable_encoder(response)
            if method == "POST" and path.startswith("/expedientes/") and path.endswith("/release-receipts"):
                expediente_id = path.split("/")[2]
                release_payload = schemas.ReleaseReceiptCreate(**(payload or {}))
                response = routes.create_release_receipt(
                    expediente_id=expediente_id,
                    payload=release_payload,
                    request=fake_request(path, "POST"),
                    current_user=user,
                    db=session,
                )
                return jsonable_encoder(response)
            raise AssertionError(f"Unhandled dispatch route: {method} {path}")
        finally:
            session.close()

    return dispatch


def test_workspace_flow_end_to_end(app_bundle: dict[str, object], make_user, monkeypatch) -> None:
    admin = make_user(
        email="admin@example.com",
        display_name="Admin",
        role=app_bundle["enums"].UserRole.ADMIN,
    )
    expediente = create_expediente(app_bundle, admin["user"])
    create_source_document(app_bundle, admin["user"], str(expediente.id))

    import scripts.run_operator_console as workspace

    dispatcher = build_backend_dispatch(app_bundle, admin["user"])
    monkeypatch.setattr(workspace, "backend_request", dispatcher)

    ollama_outputs = iter(
        [
            {
                "message": {
                    "content": (
                        "1. Expediente Snapshot\n2. Hechos Confirmados\n3. Cronologia Relevante\n"
                        "4. Documentos Clave del Expediente\n5. Control Previo Antes del Fondo\n"
                        "6. Huecos de Informacion\n7. Siguiente Paso Operativo"
                    )
                }
            },
            {
                "message": {
                    "content": (
                        '{"summary_status":"acreditado","summary_note":"Base suficiente",'
                        '"items":['
                        '{"key":"personalidad","status":"acreditado","evidence":"Demanda","risk":"","next_action":"Ninguna"},'
                        '{"key":"personeria","status":"acreditado","evidence":"Demanda","risk":"","next_action":"Ninguna"},'
                        '{"key":"poderes","status":"acreditado","evidence":"Anexo","risk":"","next_action":"Ninguna"},'
                        '{"key":"legitimacion","status":"acreditado","evidence":"Hechos","risk":"","next_action":"Ninguna"},'
                        '{"key":"competencia","status":"acreditado","evidence":"Autoridad","risk":"","next_action":"Ninguna"},'
                        '{"key":"via","status":"acreditado","evidence":"Demanda","risk":"","next_action":"Ninguna"},'
                        '{"key":"emplazamiento_notificacion","status":"acreditado","evidence":"Constancia","risk":"","next_action":"Ninguna"},'
                        '{"key":"fechas_clave","status":"acreditado","evidence":"Cronologia","risk":"","next_action":"Ninguna"},'
                        '{"key":"plazos_preclusion","status":"acreditado","evidence":"Computo","risk":"","next_action":"Ninguna"}'
                        "]}"
                    )
                }
            },
            {
                "message": {
                    "content": (
                        "1. Base Documental Usada\n- Demanda inicial\n\n"
                        "2. Huecos y Supuestos\n- Ninguno relevante\n\n"
                        "3. Nivel de Confianza\n- alto: soporte suficiente\n\n"
                        "4. Borrador de la Seccion\nAntecedentes del asunto..."
                    )
                }
            },
            {
                "message": {
                    "content": (
                        '{"change_scope":"narrow","confidence":"alto",'
                        '"justification":["Aclara secuencia","Depura redundancia"],'
                        '"revised_text":"Antecedentes del asunto, version revisada."}'
                    )
                }
            },
            {
                "message": {
                    "content": (
                        '{"summary_status":"defendable","summary_note":"Soporte suficiente","items":['
                        '{"claim":"Existe interes juridico","support_status":"acreditado",'
                        '"evidence_basis":"Demanda inicial","expediente_support":"Hechos confirmados",'
                        '"missing_for_court":""}'
                        "]}"
                    )
                }
            },
            {
                "message": {
                    "content": (
                        '{"summary_status":"defendable","summary_note":"Soporte suficiente","items":['
                        '{"claim":"Existe interes juridico","support_status":"acreditado",'
                        '"evidence_basis":"Demanda inicial","expediente_support":"Hechos confirmados",'
                        '"missing_for_court":""}'
                        "]}"
                    )
                }
            },
        ]
    )

    monkeypatch.setattr(workspace, "run_ollama_chat", lambda _messages: next(ollama_outputs))

    synthesis_handler = FakeHandler(
        {
            "title": "Sintesis vigente del expediente",
            "objective": "Ordena el expediente para trabajo posterior.",
        }
    )
    workspace.OperatorConsoleHandler.handle_workspace_case_analysis(synthesis_handler, str(expediente.id))
    assert synthesis_handler.status == HTTPStatus.CREATED
    assert synthesis_handler.response["synthesis"]["title"] == "Sintesis vigente del expediente"

    checklist_handler = FakeHandler({"objective": "Audita control previo."})
    workspace.OperatorConsoleHandler.handle_workspace_preflight_checklist(checklist_handler, str(expediente.id))
    assert checklist_handler.status == HTTPStatus.CREATED
    assert checklist_handler.response["checklist"]["summary_status"] == "acreditado"

    draft_handler = FakeHandler(
        {
            "bundle_title": "Demanda de amparo",
            "document_type": "demanda",
            "section_key": "antecedentes",
            "prompt": "Redacta antecedentes breves y claros.",
        }
    )
    workspace.OperatorConsoleHandler.handle_workspace_draft(draft_handler, str(expediente.id))
    assert draft_handler.status == HTTPStatus.CREATED
    drafted_document = draft_handler.response["document"]
    drafted_version_id = drafted_document["versions"][-1]["id"]

    revision_handler = FakeHandler(
        {
            "document_version_id": drafted_version_id,
            "revision_mode": "narrow",
            "objective": "Corrige estilo sin reescribir todo.",
        }
    )
    workspace.OperatorConsoleHandler.handle_workspace_revision(revision_handler, str(expediente.id))
    assert revision_handler.status == HTTPStatus.CREATED
    revised_version_id = revision_handler.response["document_version_id"]
    assert revision_handler.response["changed"] is True

    defendability_handler = FakeHandler({"document_version_id": revised_version_id})
    workspace.OperatorConsoleHandler.handle_workspace_defendability_gate(defendability_handler, str(expediente.id))
    assert defendability_handler.status == HTTPStatus.CREATED
    assert defendability_handler.response["gate"]["summary_status"] == "defendable"

    release_handler = FakeHandler(
        {
            "document_version_id": revised_version_id,
            "verdict": "approved",
            "response_type": "workspace_manual_review",
            "notes": "Liberado tras revision interna.",
        }
    )
    workspace.OperatorConsoleHandler.handle_workspace_release(release_handler, str(expediente.id))
    assert release_handler.status == HTTPStatus.CREATED
    assert release_handler.response["verdict"] == "approved"
    assert release_handler.response["gate_summary"]["defendability_gate"]["summary_status"] == "defendable"
