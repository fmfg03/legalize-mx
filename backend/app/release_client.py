"""Authenticated client for CLI and workspace; no local approval or shared-key fallback."""
from __future__ import annotations

from contextlib import asynccontextmanager
from ipaddress import ip_address
from urllib.parse import urlsplit

import httpx2
from mcp import Client
from mcp.client.streamable_http import streamable_http_client


def validate_endpoint(url: str) -> None:
    parsed = urlsplit(url)
    try:
        loopback = parsed.hostname == "localhost" or ip_address(parsed.hostname or "").is_loopback
    except ValueError:
        loopback = False
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path != "/mcp" or not parsed.hostname or (parsed.scheme != "https" and not (parsed.scheme == "http" and loopback)):
        raise ValueError("MCP endpoint must use HTTPS or loopback HTTP and identify /mcp")


@asynccontextmanager
async def bearer_transport(endpoint: str, access_token: str):
    if not access_token or any(c in access_token for c in "\r\n"):
        raise ValueError("Authenticated session bearer required")
    validate_endpoint(endpoint)
    async with httpx2.AsyncClient(headers={"Authorization": f"Bearer {access_token}"}, timeout=30) as http:
        async with streamable_http_client(endpoint, http_client=http) as streams:
            yield streams


async def call_release_tool(endpoint: str, access_token: str, name: str, *, expediente_id: str, payload: dict) -> dict:
    if name not in {"evaluate_document_release", "release_document"}:
        raise ValueError("Unsupported protected release operation")
    async with Client(bearer_transport(endpoint, access_token), read_timeout_seconds=45) as client:
        result = await client.call_tool(name, {"expediente_id": expediente_id, "payload": payload})
        if result.is_error:
            message = result.content[0].text if result.content else "Protected release operation failed"
            raise ValueError(message)
        if not isinstance(result.structured_content, dict):
            raise ValueError("Server returned no structured release evidence")
        return result.structured_content


async def evaluate_and_release(endpoint: str, access_token: str, *, expediente_id: str, document_version_id: str, bundle: dict) -> dict:
    async with Client(bearer_transport(endpoint, access_token), read_timeout_seconds=45) as client:
        evaluation = await client.call_tool("evaluate_document_release", {"expediente_id": expediente_id, "payload": {"document_version_id": document_version_id, "bundle": bundle}})
        if evaluation.is_error or not isinstance(evaluation.structured_content, dict):
            raise ValueError("Server rejected gate evaluation")
        result = evaluation.structured_content
        if result["verdict"] != "approved":
            return {"release_verdict": "BLOCKED", "evaluation": result}
        receipt = await client.call_tool("release_document", {"expediente_id": expediente_id, "payload": {"execution_id": result["id"], "bundle": bundle}})
        if receipt.is_error or not isinstance(receipt.structured_content, dict):
            raise ValueError("Server rejected release evidence")
        persisted = receipt.structured_content
        if persisted["verdict"] != "approved" or persisted.get("execution_id") != result["id"]:
            raise ValueError("Server receipt does not match approved execution")
        return {"release_verdict": "APPROVED", "evaluation": result, "receipt": persisted}
