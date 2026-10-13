from __future__ import annotations

from urllib.parse import urlsplit
import uuid

from fastapi import HTTPException

from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

from backend.app.config import Settings
from backend.app.mcp_auth import JWTVerifier, invocation_capabilities
from backend.app.schemas.expedientes import ReleaseEvaluationCreate, ReleaseReceiptCreate, ReleaseReceiptRead, ReleaseEvaluationRead
from backend.app.release_service import evaluate_release, release_from_execution


def build_mcp_server(config: Settings, session_factory) -> MCPServer:
    verifier = JWTVerifier(config, session_factory)
    server = MCPServer(
        "legalize-mx", token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=config.oauth_issuer, resource_server_url=config.oauth_resource_url,
            required_scopes=["legalize:read"], validate_token_resource=True,
        ),
    )

    @server.tool()
    def whoami() -> dict[str, str]:
        """Return the local actor established by authenticated HTTP context."""
        with session_factory() as db:
            capabilities = invocation_capabilities(db)
            if not capabilities.can_read:
                raise ToolError("Read scope required")
            return {"actor_id": str(capabilities.actor_id)}

    @server.tool()
    def evaluate_document_release(expediente_id: uuid.UUID, payload: ReleaseEvaluationCreate) -> ReleaseEvaluationRead:
        """Execute required gates on a persisted document version; return server evidence."""
        with session_factory() as db:
            capabilities = invocation_capabilities(db)
            if not capabilities.can_release:
                raise ToolError("Release scope and reviewer role required")
            try:
                execution = evaluate_release(db=db, actor_id=capabilities.actor_id, expediente_id=expediente_id, **payload.model_dump())
                return ReleaseEvaluationRead.model_validate(execution)
            except HTTPException as exc:
                raise ToolError(str(exc.detail)) from exc

    @server.tool()
    def release_document(expediente_id: uuid.UUID, payload: ReleaseReceiptCreate) -> ReleaseReceiptRead:
        """Consume matching server gate evidence and persist a release receipt and outbox event."""
        with session_factory() as db:
            capabilities = invocation_capabilities(db)
            if not capabilities.can_release:
                raise ToolError("Release scope and reviewer role required")
            try:
                receipt = release_from_execution(db=db, actor_id=capabilities.actor_id, expediente_id=expediente_id, **payload.model_dump())
                return ReleaseReceiptRead.model_validate(receipt)
            except HTTPException as exc:
                raise ToolError(str(exc.detail)) from exc

    return server


def build_mcp_app(config: Settings, session_factory):
    server = build_mcp_server(config, session_factory)
    resource = urlsplit(config.oauth_resource_url)
    return server.streamable_http_app(
        stateless_http=True, json_response=True,
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=[resource.netloc], allowed_origins=[f"{resource.scheme}://{resource.netloc}"],
        ),
    )
