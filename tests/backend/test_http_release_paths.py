from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib
import ipaddress
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import httpx
import pytest
import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from test_mcp_auth import oauth  # Shared synthetic identity fixture, no production credential.


@pytest.fixture
def live_http(app_bundle, oauth, monkeypatch, tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "legalize-slice0-synthetic-test")])
    cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=1))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(hours=1))
        .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True).sign(key, hashes.SHA256()))
    cert_path, key_path = tmp_path / "synthetic-ca.pem", tmp_path / "synthetic-tls-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    key_path.chmod(0o600)
    monkeypatch.setenv("SSL_CERT_FILE", str(cert_path))
    public_keys = {"keys": [oauth["public"]]}
    requests = []

    class JWKS(BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.path)
            self.send_response(200 if public_keys["keys"] is not None else 503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(public_keys).encode())
        def log_message(self, *_):
            pass

    jwks = ThreadingHTTPServer(("127.0.0.1", 0), JWKS)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert_path, key_path)
    jwks.socket = tls.wrap_socket(jwks.socket, server_side=True)
    jwks_thread = threading.Thread(target=jwks.serve_forever, daemon=True)
    jwks_thread.start()
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    port = listener.getsockname()[1]
    listener.listen(128)
    config = oauth["config"]
    config.oauth_issuer = f"https://127.0.0.1:{jwks.server_port}"
    config.oauth_jwks_url = config.oauth_issuer + "/jwks"
    config.oauth_resource_url = f"https://127.0.0.1:{port}/mcp"
    config_module = importlib.import_module("backend.app.config")
    monkeypatch.setattr(config_module, "settings", config)
    # Bindings use exact issuer; their update is confined to the synthetic test database.
    with app_bundle["db"].SessionLocal() as db:
        for binding in db.query(app_bundle["models"].OAuthBinding).all():
            binding.issuer = config.oauth_issuer
        db.commit()
    main = importlib.reload(importlib.import_module("backend.app.main"))
    server = uvicorn.Server(uvicorn.Config(main.app, log_level="error", ssl_certfile=str(cert_path), ssl_keyfile=str(key_path)))
    thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(.02)
    assert server.started, "Synthetic HTTPS server failed to start"
    workspace = importlib.import_module("scripts.run_operator_console")
    monkeypatch.setattr(workspace, "MCP_URL", config.oauth_resource_url)
    monkeypatch.setattr(workspace, "API_BASE_URL", config.oauth_resource_url.removesuffix("/mcp") + "/api/v1")
    monkeypatch.setattr(workspace, "API_KEY", oauth["actors"][0]["plaintext_api_key"])
    console = ThreadingHTTPServer(("127.0.0.1", 0), workspace.OperatorConsoleHandler)
    console_thread = threading.Thread(target=console.serve_forever, daemon=True)
    console_thread.start()
    actor = oauth["actors"][0]["user"]
    schemas = importlib.import_module("backend.app.schemas.expedientes")
    req = SimpleNamespace(url=SimpleNamespace(path="/test"), method="POST")
    bundle = {"response_type": "recommendation", "response_text": "Synthetic release document with no legal claims.", "citations": [], "claims": []}
    with app_bundle["db"].SessionLocal() as db:
        expediente = app_bundle["expediente_routes"].create_expediente(payload=schemas.ExpedienteCreate(title="Synthetic HTTPS release", matter_type="amparo"), request=req, current_user=actor, db=db)
        detail = app_bundle["expediente_routes"].create_document(expediente_id=str(expediente.id), request=req, current_user=actor, db=db,
            payload=schemas.DocumentWithVersionCreate(document={"document_type": "escrito", "title": "Document"}, version={"source_kind": "generated", "file_name": "response.txt", "content_base64": base64.b64encode(bundle["response_text"].encode()).decode()}))
        expediente_id, version_id = str(expediente.id), str(detail.documents[0].versions[0].id)
    try:
        yield dict(oauth=oauth, mcp=config.oauth_resource_url, console=f"http://127.0.0.1:{console.server_port}",
            expediente_id=expediente_id, version_id=version_id, bundle=bundle, cert=cert_path, jwks_requests=requests, jwks=public_keys)
    finally:
        console.shutdown()
        console.server_close()
        console_thread.join(5)
        server.should_exit = True
        thread.join(5)
        listener.close()
        jwks.shutdown()
        jwks.server_close()
        jwks_thread.join(5)


def mcp_call(live, name, payload, token=None):
    with httpx.Client(verify=ssl.create_default_context(cafile=str(live["cert"]))) as client:
        headers = {"Accept": "application/json, text/event-stream", "MCP-Protocol-Version": "2025-11-25"}
        if token:
            headers["Authorization"] = "Bearer " + token
        return client.post(live["mcp"], headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": {"expediente_id": live["expediente_id"], "payload": payload}, "_meta": {"actor_id": "ignored", "role": "admin"}}})


def test_real_https_jwks_and_consecutive_actors_fail_closed(live_http):
    live = live_http
    evaluate = {"document_version_id": live["version_id"], "bundle": live["bundle"]}
    assert mcp_call(live, "evaluate_document_release", evaluate).status_code == 401
    assert mcp_call(live, "evaluate_document_release", evaluate, "invalid").status_code == 401
    first = mcp_call(live, "evaluate_document_release", evaluate, live["oauth"]["token"]())
    assert first.status_code == 200, first.text
    execution_id = first.json()["result"]["structuredContent"]["id"]
    release = {"execution_id": execution_id, "bundle": live["bundle"]}
    second = mcp_call(live, "release_document", release, live["oauth"]["token"](sub="subject-1"))
    assert second.json()["result"]["isError"] is True
    missing = mcp_call(live, "release_document", {**release, "execution_id": "00000000-0000-0000-0000-000000000001"}, live["oauth"]["token"]())
    assert missing.json()["result"]["isError"] is True
    approved = mcp_call(live, "release_document", release, live["oauth"]["token"]())
    assert approved.json()["result"]["structuredContent"]["verdict"] == "approved"
    assert "/jwks" in live["jwks_requests"]


def test_cli_and_workspace_use_authenticated_persistent_release(live_http, tmp_path):
    live = live_http
    path = tmp_path / "bundle.json"
    path.write_text(json.dumps(live["bundle"]))
    args = [sys.executable, "scripts/release_legal_response.py", "--bundle", str(path), "--expediente-id", live["expediente_id"], "--document-version-id", live["version_id"], "--mcp-url", live["mcp"]]
    env = {**os.environ, "LEGALIZE_MX_SESSION_BEARER": live["oauth"]["token"](), "SSL_CERT_FILE": str(live["cert"])}
    result = subprocess.run(args, capture_output=True, text=True, env=env, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    persisted = json.loads(result.stdout)
    assert persisted["release_verdict"] == "APPROVED" and persisted["receipt"]["execution_id"]
    missing = subprocess.run(args, capture_output=True, text=True, env={**env, "LEGALIZE_MX_SESSION_BEARER": ""}, timeout=15)
    assert missing.returncode == 2
    assert json.loads(missing.stdout)["release_verdict"] == "ERROR"
    for forbidden in ("--authority-live-fixture", "--release-policy", "--release-dir"):
        refused = subprocess.run(args + [forbidden, str(path)], capture_output=True, text=True, env=env, timeout=15)
        assert refused.returncode == 2
    url = f"{live['console']}/app-api/expedientes/{live['expediente_id']}/release"
    evaluation_body = {"action": "evaluate", "document_version_id": live["version_id"], "bundle": live["bundle"]}
    assert httpx.post(url, json=evaluation_body).status_code == 401
    headers = {"Authorization": "Bearer " + live["oauth"]["token"]()}
    assert httpx.post(url, headers=headers, json={"verdict": "approved", "document_version_id": live["version_id"]}).status_code == 422
    evaluation = httpx.post(url, headers=headers, json=evaluation_body, timeout=30)
    assert evaluation.status_code == 201, evaluation.text
    receipt = httpx.post(url, headers=headers, json={"action": "release", "execution_id": evaluation.json()["id"], "bundle": live["bundle"]}, timeout=30)
    assert receipt.status_code == 201, receipt.text
    assert receipt.json()["created_by_user_id"] == str(live["oauth"]["actors"][0]["user"].id)
    repeat = httpx.post(url, headers=headers, json={"action": "release", "execution_id": evaluation.json()["id"], "bundle": live["bundle"]}, timeout=30)
    assert repeat.json()["id"] == receipt.json()["id"]


def test_workspace_browser_session_and_server_gates(live_http, tmp_path):
    live = live_http
    fixture = tmp_path / "browser-fixture.json"
    fixture.write_text(json.dumps({"console": live["console"], "versionId": live["version_id"], "bundle": live["bundle"],
        "firstToken": live["oauth"]["token"](), "secondToken": live["oauth"]["token"](sub="subject-1"),
        "secondActorId": str(live["oauth"]["actors"][1]["user"].id)}))
    result = subprocess.run(["node", "tests/workspace_release_browser.cjs"], env={**os.environ, "LEGALIZE_BROWSER_FIXTURE": str(fixture)}, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    proof = json.loads(result.stdout)
    assert proof["session_and_bundle_invalidation"] is True
    assert proof["page_errors"] == 0


def test_panel_skip_release_never_emits_final_approved(tmp_path):
    root = Path(__file__).parents[2]
    args = [sys.executable, "scripts/legal_panel_orchestrator.py", "--session", "fixtures/legal_panel_session_pass.json",
        "--root", str(root), "--policy", "config/legal_panel_policy.json", "--routing-policy", "config/hybrid_model_routing_policy.json",
        "--receipt-log", str(tmp_path / "panel.jsonl"), "--artifact-dir", str(tmp_path / "artifacts"), "--skip-release"]
    result = subprocess.run(args, capture_output=True, text=True, timeout=15)
    assert result.returncode == 1, result.stdout + result.stderr
    output = json.loads(result.stdout)
    assert output["panel_verdict"] == "RELEASE_PENDING"
    assert output["release_result"] is None
    result = subprocess.run(args[:-1], capture_output=True, text=True, timeout=15)
    assert result.returncode == 1
    assert json.loads(result.stdout)["panel_verdict"] == "BLOCKED"
