#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPOSITORY_BASE = "https://bicentenario.scjn.gob.mx/repositorio-scjn"
REFORMA_API_BASE = f"{REPOSITORY_BASE}/api/reforma"
JURISPRUDENCE_API_BASE = f"{REPOSITORY_BASE}/api/v1"
GROUP_ID_BY_DOCUMENT_KIND = {
    "tesis": 1,
    "precedente": 1,
    "voto": 1,
    "acuerdo": 1,
}
LABEL_BY_DOCUMENT_KIND = {
    "tesis": "Tesis",
    "precedente": "Precedente",
    "voto": "Votos",
    "acuerdo": "Acuerdo",
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_space(value: Any) -> str:
    return " ".join(str(value or "").split())


def fetch_json(url: str, timeout: int) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "legalize-mx/0.1 (+https://bicentenario.scjn.gob.mx/repositorio-scjn)",
        },
        method="GET",
    )
    context = ssl.create_default_context()
    with urllib.request.urlopen(request, timeout=timeout, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def get_fuentes(group_id: int, timeout: int) -> list[dict[str, Any]]:
    return fetch_json(f"{REFORMA_API_BASE}/fuentes/{group_id}", timeout)


def resolve_fuente(document_kind: str, timeout: int) -> dict[str, Any]:
    group_id = GROUP_ID_BY_DOCUMENT_KIND[document_kind]
    expected_label = LABEL_BY_DOCUMENT_KIND[document_kind].lower()
    for fuente in get_fuentes(group_id, timeout):
        etiqueta = str(fuente.get("etiqueta") or "").strip().lower()
        if etiqueta == expected_label:
            return fuente
    raise SystemExit(f"No se encontro fuente para document_kind={document_kind!r} en idGrupo={group_id}.")


def get_count(indice: str, timeout: int) -> int:
    value = fetch_json(f"{JURISPRUDENCE_API_BASE}/{indice}/count", timeout)
    return int(value)


def get_ids(indice: str, page: int, size: int, timeout: int) -> list[str]:
    params = urllib.parse.urlencode({"page": page, "size": size})
    payload = fetch_json(f"{JURISPRUDENCE_API_BASE}/{indice}/ids?{params}", timeout)
    return [str(item).strip() for item in payload if str(item).strip()]


def get_document(indice: str, registry_id: str, timeout: int) -> dict[str, Any]:
    return fetch_json(f"{JURISPRUDENCE_API_BASE}/{indice}/{registry_id}", timeout)


def get_default_document(indice: str, timeout: int) -> dict[str, Any]:
    return fetch_json(f"{JURISPRUDENCE_API_BASE}/{indice}/default", timeout)


def normalize_first_detail(payload: dict[str, Any], fuente: dict[str, Any], retrieved_at: str) -> dict[str, Any]:
    identifier_key = str(fuente.get("identificador") or "").strip()
    registry_id = str(payload.get(identifier_key) or payload.get("registry_id") or "").strip()
    citation_parts = [normalize_space(payload.get("tesis")), f"registro digital {registry_id}"]
    citation_label = " | ".join(part for part in citation_parts if part and part != "registro digital")
    if not citation_label:
        citation_label = f"Tesis con registro digital {registry_id}"
    return {
        "registry_id": registry_id or None,
        "title": normalize_space(payload.get("rubro")),
        "citation_label": citation_label,
        "type": normalize_space(payload.get("tipoTesis")),
        "epoch": normalize_space(payload.get("epoca")),
        "instance": normalize_space(payload.get("instancia")),
        "organ": normalize_space(payload.get("organoJuris")),
        "publication_date": normalize_space(payload.get("notaPublica") or payload.get("fechaPublicado")),
        "source_url": f"{JURISPRUDENCE_API_BASE}/{fuente['indice']}/{registry_id}" if registry_id else None,
        "retrieved_at": retrieved_at,
    }


def build_items(indice: str, *, count_total: int, page_size: int, start_page: int, max_pages: int, max_items: int | None, timeout: int) -> tuple[list[dict[str, Any]], int]:
    items: list[dict[str, Any]] = []
    total_pages = max(1, math.ceil(count_total / page_size)) if count_total else 0
    if start_page >= total_pages:
        return items, 0
    remaining_pages = total_pages - start_page
    pages_target = remaining_pages if max_pages <= 0 else min(remaining_pages, max_pages)
    pages_fetched = 0
    for page in range(start_page, start_page + pages_target):
        ids = get_ids(indice, page=page, size=page_size, timeout=timeout)
        pages_fetched += 1
        for offset, registry_id in enumerate(ids):
            items.append(
                {
                    "registry_id": registry_id,
                    "page": page,
                    "page_size": page_size,
                    "position_in_page": offset,
                    "source_url": f"{JURISPRUDENCE_API_BASE}/{indice}/{registry_id}",
                }
            )
            if max_items is not None and len(items) >= max_items:
                return items, pages_fetched
        if not ids:
            break
    return items, pages_fetched


def main() -> int:
    parser = argparse.ArgumentParser(description="Descubre catalogos jurisprudenciales desde la API oficial del Repositorio SCJN.")
    parser.add_argument("--document-kind", default="tesis", choices=["tesis", "precedente", "voto", "acuerdo"])
    parser.add_argument("--page-size", type=int, default=1000, help="Tamanio de pagina para /ids. La UI indica maximo 1000.")
    parser.add_argument("--start-page", type=int, default=0, help="Pagina inicial de /ids.")
    parser.add_argument("--max-pages", type=int, default=1, help="Numero maximo de paginas a consultar. Usa 0 para todas.")
    parser.add_argument("--max-items", type=int, default=None, help="Corta el listado tras N ids si se especifica.")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--output", default=None, help="Ruta del catalogo JSON a escribir.")
    args = parser.parse_args()

    output = Path(args.output or f"/root/legalize-mx/raw/scjn/catalog/{args.document_kind}_catalog.json")
    output.parent.mkdir(parents=True, exist_ok=True)

    retrieved_at = utc_now_iso()
    fuente = resolve_fuente(args.document_kind, args.timeout)
    indice = str(fuente["indice"])
    count_total = get_count(indice, args.timeout)
    items, pages_fetched = build_items(
        indice,
        count_total=count_total,
        page_size=args.page_size,
        start_page=args.start_page,
        max_pages=args.max_pages,
        max_items=args.max_items,
        timeout=args.timeout,
    )
    default_document = get_default_document(indice, args.timeout)
    first_detail = normalize_first_detail(default_document, fuente, retrieved_at)

    payload = {
        "generated_at": retrieved_at,
        "source_system": "scjn_bicentenario_repository",
        "document_kind": args.document_kind,
        "status": "ok",
        "source_endpoint": f"{REFORMA_API_BASE}/fuentes/{fuente['idGrupo']}",
        "source_index": indice,
        "fuente_definition": fuente,
        "api_contract": {
            "count": f"{JURISPRUDENCE_API_BASE}/{indice}/count",
            "ids": f"{JURISPRUDENCE_API_BASE}/{indice}/ids?page={{page}}&size={{size}}",
            "default": f"{JURISPRUDENCE_API_BASE}/{indice}/default",
            "detail": f"{JURISPRUDENCE_API_BASE}/{indice}/{{registry_id}}",
        },
        "count_total": count_total,
        "page_size": args.page_size,
        "start_page": args.start_page,
        "pages_fetched": pages_fetched,
        "items_truncated": args.max_items is not None or (count_total and (args.start_page > 0 or (args.max_pages > 0 and args.start_page + pages_fetched < max(1, math.ceil(count_total / args.page_size))))),
        "items": items,
        "first_detail": first_detail,
        "default_document_raw": default_document,
        "notes": [
            "Este catalogo usa la API oficial del Repositorio de la SCJN publicada en bicentenario.scjn.gob.mx/repositorio-scjn.",
            "La ruta del frontend SJF carga getFuentes(1) y resuelve `tesis` como indice del API v1.",
        ],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "ok": True,
                "status": payload["status"],
                "output": str(output),
                "document_kind": args.document_kind,
                "source_index": indice,
                "count_total": count_total,
                "items": len(items),
                "pages_fetched": pages_fetched,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
