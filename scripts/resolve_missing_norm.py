#!/usr/bin/env python3
"""
Resuelve consultas de normas fuera del stack local hacia conectores configurados.

No descarga documentos. Solo:
1. busca en el manifiesto local
2. si no encuentra, busca un conector compatible
3. opcionalmente encola una solicitud de materializacion futura
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
LEGISLATION_MANIFEST = REPO_ROOT / "indexes" / "legislation_manifest.jsonl"
CONNECTORS_REGISTRY = REPO_ROOT / "sources" / "on_demand_connectors.json"
STATE_CONNECTORS_BASE = REPO_ROOT / "sources" / "state_connectors_base.json"
REQUESTS_DIR = REPO_ROOT / "raw" / "on_demand" / "queue"
REQUESTS_PATH = REQUESTS_DIR / "missing_norm_requests.jsonl"
WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    return WS_RE.sub(" ", text.strip().lower())


def load_manifest() -> list[dict[str, Any]]:
    if not LEGISLATION_MANIFEST.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in LEGISLATION_MANIFEST.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def load_connectors() -> list[dict[str, Any]]:
    base_payload = json.loads(STATE_CONNECTORS_BASE.read_text(encoding="utf-8"))
    registry_payload = json.loads(CONNECTORS_REGISTRY.read_text(encoding="utf-8"))

    overridden: dict[str, dict[str, Any]] = {}
    for connector in registry_payload.get("connectors", []):
        state_code = connector.get("state_code")
        if state_code:
            overridden[str(state_code)] = connector

    connectors: list[dict[str, Any]] = []
    for state in base_payload.get("states", []):
        state_code = state["state_code"]
        if state_code in overridden:
            connectors.append(overridden[state_code])
            continue
        edo_id = state.get("edo_id")
        all_types_url = f"https://www.ordenjuridico.gob.mx/despliegaedo2.php?edo={edo_id}"
        code_url = f"https://www.ordenjuridico.gob.mx/despliegaedo2.php?catTipo=5&edo={edo_id}&ordenar="
        regulation_url = f"https://www.ordenjuridico.gob.mx/despliegaedo2.php?catTipo=6&edo={edo_id}&ordenar="
        connectors.append(
            {
                "connector_id": f"ojn_state_{state_code}",
                "display_name": f"Orden Juridico Nacional - {state['state_name']}",
                "jurisdiction": "state",
                "state_code": state_code,
                "connector_status": "verified_ojn_fallback",
                "source_classification": "informative_compilation",
                "official_source_name": "Orden Juridico Nacional / fuente oficial local segun entidad",
                "officiality_notice": "El Orden Juridico Nacional es informativo. La validez juridica corresponde al medio oficial de publicacion de la entidad federativa.",
                "listing_urls": {
                    "all_types": all_types_url,
                    "law": all_types_url,
                    "code": code_url,
                    "regulation": regulation_url,
                    "constitution": "https://www.ordenjuridico.gob.mx/constitucionEdo.php",
                },
                "detail_url_templates": {},
                "match_aliases": state.get("match_aliases", []),
                "seeded_targets": [],
                "ojn_edo_id": edo_id,
            }
        )

    for connector in registry_payload.get("connectors", []):
        if connector.get("state_code") not in overridden:
            connectors.append(connector)
    return connectors


def find_local_match(query: str, manifest: list[dict[str, Any]]) -> dict[str, Any] | None:
    normalized_query = normalize(query)
    exact_hits: list[dict[str, Any]] = []
    fuzzy_hits: list[dict[str, Any]] = []
    for record in manifest:
        title = record.get("title") or ""
        short_title = record.get("short_title") or ""
        haystack = " ".join([normalize(title), normalize(short_title)])
        if normalized_query == normalize(title) or normalized_query == normalize(short_title):
            exact_hits.append(record)
        elif normalized_query in haystack or haystack in normalized_query:
            fuzzy_hits.append(record)
    if exact_hits:
        return exact_hits[0]
    if fuzzy_hits:
        return fuzzy_hits[0]
    return None


def connector_matches_scope(
    connector: dict[str, Any],
    jurisdiction: str | None,
    state_code: str | None,
    query: str,
) -> bool:
    if jurisdiction and connector.get("jurisdiction") != jurisdiction:
        return False
    connector_state = connector.get("state_code")
    if state_code and connector_state != state_code:
        return False
    if connector_state and connector_state == state_code:
        return True
    normalized_query = normalize(query)
    aliases = [normalize(alias) for alias in connector.get("match_aliases", [])]
    return any(alias in normalized_query for alias in aliases)


def find_external_target(
    query: str,
    connectors: list[dict[str, Any]],
    jurisdiction: str | None,
    state_code: str | None,
    document_type: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    normalized_query = normalize(query)
    compatible_connectors: list[dict[str, Any]] = []

    for connector in connectors:
        if connector_matches_scope(connector, jurisdiction, state_code, query):
            compatible_connectors.append(connector)

    for connector in compatible_connectors:
        for target in connector.get("seeded_targets", []):
            if document_type and target.get("document_type") != document_type:
                continue
            aliases = [normalize(target.get("title") or "")]
            aliases.extend(normalize(alias) for alias in target.get("aliases", []))
            if normalized_query in aliases or any(alias in normalized_query for alias in aliases):
                return connector, target

    if compatible_connectors:
        return compatible_connectors[0], None
    return None, None


def append_request(record: dict[str, Any]) -> Path:
    REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    enriched = {
        "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        **record,
    }
    with REQUESTS_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(enriched, ensure_ascii=True) + "\n")
    return REQUESTS_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description="Resuelve una norma faltante hacia un conector configurado.")
    parser.add_argument("--query", required=True, help="Consulta normativa, por ejemplo 'Codigo Civil de Tamaulipas'")
    parser.add_argument("--jurisdiction", choices=["federal", "state", "municipal"], help="Ambito juridico esperado")
    parser.add_argument("--state-code", help="Codigo de estado, por ejemplo tam")
    parser.add_argument("--document-type", choices=["law", "code", "regulation"], help="Tipo de documento")
    parser.add_argument("--enqueue", action="store_true", help="Encola la solicitud para materializacion futura")
    args = parser.parse_args()

    manifest = load_manifest()
    connectors = load_connectors()
    local_hit = find_local_match(args.query, manifest)
    normalized_query = normalize(args.query)

    if local_hit:
        output = {
            "resolution": "local_hit",
            "query": args.query,
            "normalized_query": normalized_query,
            "local_record": local_hit,
        }
        print(json.dumps(output, ensure_ascii=True, indent=2))
        return 0

    connector, target = find_external_target(
        args.query,
        connectors,
        args.jurisdiction,
        args.state_code,
        args.document_type,
    )

    if connector is None:
        output = {
            "resolution": "unresolved",
            "query": args.query,
            "normalized_query": normalized_query,
            "message": "No existe conector configurado para esta jurisdiccion o consulta.",
        }
        print(json.dumps(output, ensure_ascii=True, indent=2))
        return 1

    request_payload = {
        "query": args.query,
        "normalized_query": normalized_query,
        "jurisdiction": args.jurisdiction,
        "state_code": args.state_code,
        "document_type": args.document_type,
        "connector_id": connector["connector_id"],
        "connector_display_name": connector["display_name"],
    }

    output: dict[str, Any] = {
        "resolution": "external_target" if target else "connector_route",
        **request_payload,
        "connector_status": connector.get("connector_status", "unknown"),
        "source_classification": connector["source_classification"],
        "official_source_name": connector["official_source_name"],
        "officiality_notice": connector["officiality_notice"],
        "listing_urls": connector.get("listing_urls", {}),
        "recommended_action": "enqueue_materialization_request",
    }

    if target:
        output["target"] = target

    if args.enqueue:
        queue_path = append_request(output)
        output["request_queue_path"] = str(queue_path)

    print(json.dumps(output, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
