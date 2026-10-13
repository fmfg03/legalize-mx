from __future__ import annotations

import asyncio
import importlib
import time
import sys

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from mcp import Client
from mcp.client.stdio import StdioServerParameters


@pytest.fixture
def oauth(app_bundle, make_user):
    models = app_bundle["models"]
    config_module = importlib.import_module("backend.app.config")
    auth = importlib.import_module("backend.app.mcp_auth")
    server_module = importlib.import_module("backend.app.mcp_server")
    config = config_module.Settings(
        mcp_enabled=True, oauth_issuer="https://issuer.example",
        oauth_jwks_url="https://issuer.example/jwks", oauth_resource_url="https://legalize.example/mcp",
    )
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
    public.update(kid="test-key", alg="RS256", use="sig")
    actors = [make_user(email=f"mcp{i}@example.com", display_name=f"Actor {i}", role=app_bundle["enums"].UserRole.REVIEWER) for i in range(2)]
    with app_bundle["db"].SessionLocal() as db:
        for i, actor in enumerate(actors):
            db.add(models.OAuthBinding(issuer=config.oauth_issuer, subject=f"subject-{i}", user_id=actor["user"].id))
        db.commit()
    verifier = auth.JWTVerifier(config, app_bundle["db"].SessionLocal)
    verifier.jwks.fetch_data = lambda: {"keys": [public]}

    def token(**changes):
        now = int(time.time())
        claims = dict(iss=config.oauth_issuer, sub="subject-0", aud=config.oauth_resource_url,
                      exp=now + 120, nbf=now - 5, scope="legalize:read legalize:release")
        claims.update(changes)
        claims = {k: v for k, v in claims.items() if v is not None}
        return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})

    return dict(config=config, auth=auth, server=server_module, verifier=verifier, token=token, actors=actors, public=public)


def test_valid_jwt_and_rotating_jwks(oauth):
    token = oauth["token"]()
    verified = asyncio.run(oauth["verifier"].verify_token(token))
    assert verified.subject == "subject-0"
    assert verified.issuer == "https://issuer.example"
    assert verified.resource == "https://legalize.example/mcp"
    verifier = oauth["verifier"]
    verifier.jwks.fetch_data = lambda: {"keys": []}
    verifier.jwks.jwk_set_cache.put(None)
    assert asyncio.run(verifier.verify_token(token)) is None


@pytest.mark.parametrize("changes", [
    {"iss": "https://other.example"}, {"aud": "other"}, {"exp": 1},
    {"nbf": time.time() + 600}, {"exp": None}, {"nbf": None}, {"sub": None},
    {"sub": ""}, {"sub": "unbound"}, {"scope": "legalize:release"}, {"scope": ["legalize:read"]},
    {"exp": True}, {"nbf": "0"},
    {"iss": None}, {"aud": None}, {"exp": float("inf")},
    {"aud": ["other"]}, {"sub": 123}, {"nbf": float("nan")},
    {"sub": "unbound", "email": "mcp0@example.com", "actor_user_id": "subject-0", "role": "admin"},
])
def test_invalid_claims(oauth, changes):
    assert asyncio.run(oauth["verifier"].verify_token(oauth["token"](**changes))) is None


def test_invalid_signature_algorithm_and_jwks_failure(oauth):
    token = oauth["token"]()
    parts = token.split(".")
    parts[2] = ("A" if parts[2][0] != "A" else "B") + parts[2][1:]
    assert asyncio.run(oauth["verifier"].verify_token(".".join(parts))) is None
    wrong_algorithm = jwt.encode({"sub": "subject-0"}, "x" * 32, algorithm="HS256", headers={"kid": "test-key"})
    assert asyncio.run(oauth["verifier"].verify_token(wrong_algorithm)) is None
    unsigned = jwt.encode({"sub": "subject-0"}, "", algorithm="none", headers={"kid": "test-key"})
    assert asyncio.run(oauth["verifier"].verify_token(unsigned)) is None
    def offline():
        raise OSError("offline")
    oauth["verifier"].jwks.fetch_data = offline
    oauth["verifier"].jwks.jwk_set_cache.put(None)
    assert asyncio.run(oauth["verifier"].verify_token(token)) is None


@pytest.mark.parametrize("target", ["user", "binding"])
def test_inactive_identity_rejected(app_bundle, oauth, target):
    with app_bundle["db"].SessionLocal() as db:
        obj = db.get(app_bundle["models"].AppUser, oauth["actors"][0]["user"].id) if target == "user" else db.query(app_bundle["models"].OAuthBinding).filter_by(subject="subject-0").one()
        obj.is_active = False
        db.commit()
    assert asyncio.run(oauth["verifier"].verify_token(oauth["token"]())) is None


def test_http_auth_context_and_actor_isolation(app_bundle, oauth, monkeypatch):
    monkeypatch.setattr(oauth["auth"].jwt.PyJWKClient, "fetch_data", lambda _: {"keys": [oauth["public"]]})
    app = oauth["server"].build_mcp_app(oauth["config"], app_bundle["db"].SessionLocal)
    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "whoami", "arguments": {}, "_meta": {"actor_id": "attacker"}}}
    with TestClient(app, base_url="https://legalize.example") as client:
        headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25"}
        assert client.post("/mcp", json=call, headers=headers).status_code == 401
        for i in range(2):
            headers["Authorization"] = "Bearer " + oauth["token"](sub=f"subject-{i}")
            result = client.post("/mcp", json=call, headers=headers)
            assert result.status_code == 200, result.text
            assert result.json()["result"]["structuredContent"]["actor_id"] == str(oauth["actors"][i]["user"].id)
        headers["Authorization"] = "Bearer invalid"
        assert client.post("/mcp", json=call, headers=headers).status_code == 401
        metadata = client.get("/.well-known/oauth-protected-resource/mcp").json()
        assert metadata["resource"] == oauth["config"].oauth_resource_url


def test_in_memory_calls_have_no_authenticated_context(app_bundle, oauth):
    server = oauth["server"].build_mcp_server(oauth["config"], app_bundle["db"].SessionLocal)
    async def run():
        async with Client(server) as client:
            for name, arguments in unauthenticated_calls():
                result = await client.call_tool(name, arguments)
                assert result.is_error
                assert "Authenticated HTTP context required" in result.content[0].text
    asyncio.run(run())


def test_fail_closed_configuration(app_bundle):
    settings = importlib.import_module("backend.app.config").Settings
    assert settings().mcp_enabled is False
    with pytest.raises(ValueError):
        settings(mcp_enabled=True)
    with pytest.raises(ValueError):
        settings(mcp_enabled=True, oauth_issuer="https://issuer.example", oauth_jwks_url="http://issuer.example/jwks", oauth_resource_url="https://legalize.example/mcp")
    with pytest.raises(ValueError):
        settings(mcp_enabled=True, oauth_issuer="https://issuer.example", oauth_jwks_url="https://issuer.example/jwks", oauth_resource_url="https://legalize.example/mcp", oauth_algorithms=["HS256"])


def test_binding_is_unique_per_issuer_and_subject(app_bundle, oauth):
    from sqlalchemy.exc import IntegrityError
    binding = app_bundle["models"].OAuthBinding
    with app_bundle["db"].SessionLocal() as db:
        db.add(binding(issuer="https://another-issuer.example", subject="subject-0", user_id=oauth["actors"][1]["user"].id))
        db.commit()
        db.add(binding(issuer=oauth["config"].oauth_issuer, subject="subject-0", user_id=oauth["actors"][1]["user"].id))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        user = oauth["auth"].bound_user(db, oauth["config"].oauth_issuer, "subject-0")
        assert user.id == oauth["actors"][0]["user"].id
        other = oauth["auth"].bound_user(db, "https://another-issuer.example", "subject-0")
        assert other.id == oauth["actors"][1]["user"].id


def unauthenticated_calls():
    dummy = "00000000-0000-0000-0000-000000000001"
    return [
        ("whoami", {"actor_id": dummy}),
        ("evaluate_document_release", {"expediente_id": dummy, "payload": {"document_version_id": dummy, "bundle": {"actor_id": dummy}}}),
        ("release_document", {"expediente_id": dummy, "payload": {"execution_id": dummy, "bundle": {"actor_id": dummy}}}),
    ]


def test_stdio_calls_reject_identity_from_arguments(app_bundle, oauth):
    code = '''
from backend.app.config import Settings
from backend.app.db import SessionLocal
from backend.app.mcp_server import build_mcp_server
config = Settings(mcp_enabled=True, oauth_issuer="https://issuer.example", oauth_jwks_url="https://issuer.example/jwks", oauth_resource_url="https://legalize.example/mcp")
build_mcp_server(config, SessionLocal).run(transport="stdio")
'''
    async def run():
        async with Client(StdioServerParameters(command=sys.executable, args=["-c", code]), read_timeout_seconds=10) as client:
            for name, arguments in unauthenticated_calls():
                result = await client.call_tool(name, arguments)
                assert result.is_error
                assert "Authenticated HTTP context required" in result.content[0].text
    asyncio.run(run())


@pytest.mark.parametrize("restriction", ["scope", "role", "revoked_binding"])
def test_http_release_checks_current_role_scope_and_binding(app_bundle, oauth, monkeypatch, restriction):
    monkeypatch.setattr(oauth["auth"].jwt.PyJWKClient, "fetch_data", lambda _: {"keys": [oauth["public"]]})
    token = oauth["token"](scope="legalize:read" if restriction == "scope" else "legalize:read legalize:release")
    if restriction != "scope":
        with app_bundle["db"].SessionLocal() as db:
            if restriction == "role":
                user = db.get(app_bundle["models"].AppUser, oauth["actors"][0]["user"].id)
                user.role = app_bundle["enums"].UserRole.OBSERVER
            else:
                binding = db.query(app_bundle["models"].OAuthBinding).filter_by(subject="subject-0").one()
                binding.is_active = False
            db.commit()
    app = oauth["server"].build_mcp_app(oauth["config"], app_bundle["db"].SessionLocal)
    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "release_document", "arguments": {"expediente_id": "00000000-0000-0000-0000-000000000001", "payload": {"execution_id": "00000000-0000-0000-0000-000000000001", "bundle": {}}},
        "_meta": {"role": "admin", "actor_id": str(oauth["actors"][0]["user"].id)},
    }}
    with TestClient(app, base_url="https://legalize.example") as client:
        response = client.post("/mcp", json=call, headers={"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25", "Authorization": "Bearer " + token})
        if restriction == "revoked_binding":
            assert response.status_code == 401
        else:
            assert response.status_code == 200
            assert response.json()["result"]["isError"] is True
            assert "Release scope and reviewer role required" in response.json()["result"]["content"][0]["text"]


def test_mcp_release_end_to_end_builds_capabilities_once_per_invocation(app_bundle, oauth, monkeypatch):
    import base64
    from types import SimpleNamespace
    from sqlalchemy import select

    schemas = importlib.import_module("backend.app.schemas.expedientes")
    actor = oauth["actors"][0]["user"]
    bundle = {"response_type": "recommendation", "response_text": "Texto de prueba sin afirmaciones jurídicas.", "citations": [], "claims": []}
    request = SimpleNamespace(url=SimpleNamespace(path="/test"), method="POST")
    with app_bundle["db"].SessionLocal() as db:
        expediente = app_bundle["expediente_routes"].create_expediente(payload=schemas.ExpedienteCreate(title="MCP release", matter_type="amparo"), request=request, current_user=actor, db=db)
        result = app_bundle["expediente_routes"].create_document(
            expediente_id=str(expediente.id), request=request, current_user=actor, db=db,
            payload=schemas.DocumentWithVersionCreate(document={"document_type": "escrito", "title": "Texto"}, version={"source_kind": "generated", "file_name": "test.txt", "content_base64": base64.b64encode(bundle["response_text"].encode()).decode()}),
        )
        version = result.documents[0].versions[0]
    builds = []
    original = oauth["server"].invocation_capabilities
    def counted(db):
        cap = original(db)
        builds.append(cap.actor_id)
        return cap
    monkeypatch.setattr(oauth["server"], "invocation_capabilities", counted)
    monkeypatch.setattr(oauth["auth"].jwt.PyJWKClient, "fetch_data", lambda _: {"keys": [oauth["public"]]})
    app = oauth["server"].build_mcp_app(oauth["config"], app_bundle["db"].SessionLocal)
    with TestClient(app, base_url="https://legalize.example") as client:
        headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25", "Authorization": "Bearer " + oauth["token"]()}
        def call(name, payload):
            response = client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": {"expediente_id": str(expediente.id), "payload": payload}, "_meta": {"actor_id": str(actor.id)}}})
            assert response.status_code == 200, response.text
            return response.json()["result"]
        evaluation = call("evaluate_document_release", {"document_version_id": str(version.id), "bundle": bundle})
        assert "structuredContent" in evaluation, evaluation
        execution_id = evaluation["structuredContent"]["id"]
        receipt = call("release_document", {"execution_id": execution_id, "bundle": bundle})
        assert receipt["structuredContent"]["verdict"] == "approved"
        retry = call("release_document", {"execution_id": execution_id, "bundle": bundle})
        assert retry["structuredContent"]["id"] == receipt["structuredContent"]["id"]
        headers["Authorization"] = "Bearer " + oauth["token"](sub="subject-1")
        denied = call("release_document", {"execution_id": execution_id, "bundle": bundle})
        assert denied["isError"]
        assert "different actor" in denied["content"][0]["text"]
    assert builds == [actor.id, actor.id, actor.id, oauth["actors"][1]["user"].id]
    with app_bundle["db"].SessionLocal() as db:
        event = db.scalar(select(app_bundle["models"].ReleaseOutbox))
        assert event.payload["actor_user_id"] == str(actor.id)
        assert event.payload["execution_id"] == execution_id


def test_enabled_mcp_mount_uses_main_lifespan_and_auth(app_bundle, oauth, monkeypatch):
    config_module = importlib.import_module("backend.app.config")
    monkeypatch.setattr(config_module, "settings", oauth["config"])
    monkeypatch.setattr(oauth["auth"].jwt.PyJWKClient, "fetch_data", lambda _: {"keys": [oauth["public"]]})
    main = importlib.reload(importlib.import_module("backend.app.main"))
    call = {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "whoami", "arguments": {}}}
    headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25"}
    with TestClient(main.app, base_url="https://legalize.example") as client:
        assert client.post("/mcp", headers=headers, json=call).status_code == 401
        assert client.get("/.well-known/oauth-protected-resource/mcp").status_code == 200
        headers["Authorization"] = "Bearer " + oauth["token"]()
        response = client.post("/mcp", headers=headers, json=call)
        assert response.status_code == 200, response.text
        assert response.json()["result"]["structuredContent"]["actor_id"] == str(oauth["actors"][0]["user"].id)
