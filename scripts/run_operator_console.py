#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import base64
import difflib
import json
import mimetypes
import os
import posixpath
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = REPO_ROOT / "ops" / "workspace"
OPERATOR_ROOT = REPO_ROOT / "ops" / "console"
MAX_RECENT_ITEMS = 10
API_BASE_URL = os.getenv("LEXERA_API_BASE_URL", "http://127.0.0.1:8090/api/v1").rstrip("/")
API_KEY = os.getenv("LEXERA_API_KEY", "").strip()
MCP_URL = os.getenv("LEXERA_MCP_URL", "").strip()
OLLAMA_CHAT_URL = os.getenv("LEXERA_OLLAMA_CHAT_URL", "http://127.0.0.1:11434/api/chat")
OLLAMA_MODEL = os.getenv("LEXERA_OLLAMA_MODEL", "qwen3:8b")
MAX_CONTEXT_CHARS = 3500

DRAFT_SECTION_SPECS: dict[str, dict[str, str]] = {
    "antecedentes": {
        "label": "Antecedentes",
        "guidance": (
            "Reconstruye solo los antecedentes utiles para el escrito. "
            "Ordena hechos y actuaciones previas sin argumentar el fondo."
        ),
    },
    "control_procesal": {
        "label": "Control procesal previo",
        "guidance": (
            "Trabaja solo cuestiones previas y presupuestos procesales: personalidad, personeria, poderes, "
            "legitimacion, competencia, via, notificaciones, fechas criticas y plazos."
        ),
    },
    "hechos": {
        "label": "Hechos",
        "guidance": "Formula solo el apartado de hechos confirmados o alegables conforme al expediente cargado.",
    },
    "procedencia": {
        "label": "Procedencia",
        "guidance": (
            "Redacta solo el apartado de procedencia o admisibilidad, sin mezclar petitorios ni fondo."
        ),
    },
    "suspension": {
        "label": "Suspension",
        "guidance": "Redacta solo el apartado relativo a suspension, medida cautelar o tutela provisional.",
    },
    "conceptos": {
        "label": "Conceptos de violacion",
        "guidance": (
            "Trabaja solo conceptos de violacion o agravios. Si falta base normativa o documental, dilo de forma expresa."
        ),
    },
    "agravios": {
        "label": "Agravios",
        "guidance": "Redacta solo el apartado de agravios para recurso o impugnacion.",
    },
    "petitorios": {
        "label": "Petitorios",
        "guidance": "Redacta solo los puntos petitorios, congruentes con la etapa procesal y el expediente.",
    },
    "estrategia": {
        "label": "Estrategia procesal",
        "guidance": (
            "Redacta solo la seccion interna de estrategia procesal. Si el control previo esta incompleto, "
            "prioriza eso y no entres al fondo."
        ),
    },
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    return rows[-limit:]


def count_nonempty_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def file_mtime_iso(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def file_count(root: Path, pattern: str) -> int:
    if not root.exists():
        return 0
    return sum(1 for _ in root.rglob(pattern))


def safe_relpath(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def newest_files(root: Path, pattern: str, limit: int) -> list[dict[str, Any]]:
    if not root.exists():
        return []
    candidates = [path for path in root.rglob(pattern) if path.is_file()]
    candidates.sort(key=lambda item: item.stat().st_mtime, reverse=True)
    rows: list[dict[str, Any]] = []
    for path in candidates[:limit]:
        rows.append(
            {
                "path": safe_relpath(path),
                "modified_at": file_mtime_iso(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return rows


def extract_json_values(raw: str) -> list[Any]:
    values: list[Any] = []
    decoder = json.JSONDecoder()
    index = 0
    while index < len(raw):
        while index < len(raw) and raw[index].isspace():
            index += 1
        if index >= len(raw):
            break
        try:
            value, next_index = decoder.raw_decode(raw, index)
        except json.JSONDecodeError:
            break
        values.append(value)
        index = next_index
    return values


def parse_embedded_batch_summary(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    batch_summary = snapshot.get("batch_summary")
    if isinstance(batch_summary, dict):
        return batch_summary
    stdout = snapshot.get("stdout")
    if not isinstance(stdout, str) or not stdout.strip():
        return None
    values = extract_json_values(stdout)
    for value in reversed(values):
        if isinstance(value, dict):
            return value
    return None


def summarize_results(results: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"ok": 0, "partial": 0, "error": 0}
    for row in results:
        status = str(row.get("status") or "").lower()
        if status in summary:
            summary[status] += 1
    return summary


def load_latest_cycle(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        snapshot = read_json(path)
    except json.JSONDecodeError:
        return None
    batch = parse_embedded_batch_summary(snapshot)
    latest: dict[str, Any] = {
        "started_at": snapshot.get("started_at"),
        "finished_at": snapshot.get("finished_at"),
        "duration_ms": snapshot.get("duration_ms"),
        "exit_code": snapshot.get("batch_exit_code"),
    }
    if isinstance(batch, dict):
        latest["batch"] = batch
    return latest


def classify_verdict(exit_code: Any) -> str:
    if exit_code == 0:
        return "healthy"
    if exit_code is None:
        return "unknown"
    return "degraded"


def legislation_panel() -> dict[str, Any]:
    latest = load_latest_cycle(REPO_ROOT / "raw" / "diputados" / "logs" / "batch_runs" / "latest.json")
    queue_rows = read_jsonl(REPO_ROOT / "raw" / "diputados" / "queue" / "pending_downloads.jsonl")
    log_rows = tail_jsonl(REPO_ROOT / "raw" / "diputados" / "logs" / "ingestion_log.jsonl", MAX_RECENT_ITEMS)
    recent_runs = list(reversed(log_rows))
    status_breakdown = summarize_results(recent_runs)
    batch = latest.get("batch") if isinstance(latest, dict) else None
    return {
        "status": classify_verdict(latest.get("exit_code") if latest else None),
        "latest_cycle": latest,
        "latest_batch_counts": {
            "selected_count": batch.get("selected_count") if isinstance(batch, dict) else None,
            "processed": batch.get("processed") if isinstance(batch, dict) else None,
            "ok": batch.get("ok") if isinstance(batch, dict) else None,
            "partial": batch.get("partial") if isinstance(batch, dict) else None,
            "error": batch.get("error") if isinstance(batch, dict) else None,
        },
        "recent_runs": recent_runs,
        "recent_status_breakdown": status_breakdown,
        "pending_queue": {
            "count": len(queue_rows),
            "items": sorted(queue_rows, key=lambda row: int(row.get("attempt_count") or 0), reverse=True)[:MAX_RECENT_ITEMS],
        },
    }


def jurisprudence_panel() -> dict[str, Any]:
    latest = load_latest_cycle(REPO_ROOT / "raw" / "scjn" / "logs" / "batch_runs" / "latest.json")
    state_dir = REPO_ROOT / "raw" / "scjn" / "state"
    state_rows = []
    for path in sorted(state_dir.glob("*_batch_state.json")):
        try:
            state = read_json(path)
        except json.JSONDecodeError:
            continue
        state_rows.append({"path": safe_relpath(path), **state})
    latest_kinds = []
    batch = latest.get("batch") if isinstance(latest, dict) else None
    if isinstance(batch, dict):
        latest_kinds = [
            {
                "document_kind": row.get("document_kind"),
                "status": row.get("status"),
                "items": row.get("items"),
                "source_index": row.get("source_index"),
                "next_page": row.get("next_page"),
                "completed": row.get("completed"),
            }
            for row in (batch.get("kinds") or [])
            if isinstance(row, dict)
        ]
    return {
        "status": classify_verdict(latest.get("exit_code") if latest else None),
        "latest_cycle": latest,
        "states": state_rows,
        "latest_kinds": latest_kinds,
    }


def release_panel() -> dict[str, Any]:
    release_receipts = read_jsonl(REPO_ROOT / "raw" / "guardrails" / "receipts" / "legal_response_release_receipts.jsonl")
    grounding_receipts = read_jsonl(REPO_ROOT / "raw" / "guardrails" / "receipts" / "jurisprudence_grounding_gate_receipts.jsonl")
    panel_receipts = read_jsonl(REPO_ROOT / "raw" / "guardrails" / "receipts" / "legal_panel_receipts.jsonl")
    verdict_counts = {"APPROVED": 0, "BLOCKED": 0, "BYPASS": 0}
    for receipt in release_receipts:
        verdict = str(receipt.get("release_verdict") or "").upper()
        if verdict in verdict_counts:
            verdict_counts[verdict] += 1
    recent = list(reversed(release_receipts[-MAX_RECENT_ITEMS:]))
    return {
        "release_receipts_total": len(release_receipts),
        "grounding_receipts_total": len(grounding_receipts),
        "panel_receipts_total": len(panel_receipts),
        "verdict_counts": verdict_counts,
        "recent_releases": recent,
        "artifacts": {
            "approved": file_count(REPO_ROOT / "raw" / "guardrails" / "releases" / "approved", "*.json"),
            "blocked": file_count(REPO_ROOT / "raw" / "guardrails" / "releases" / "blocked", "*.json"),
            "bypass": file_count(REPO_ROOT / "raw" / "guardrails" / "releases" / "bypass", "*.json"),
        },
    }


def corpus_panel() -> dict[str, Any]:
    jurisprudence_root = REPO_ROOT / "mexico" / "jurisprudence" / "sjf"
    return {
        "indexes": {
            "legislation_manifest_rows": count_nonempty_lines(REPO_ROOT / "indexes" / "legislation_manifest.jsonl"),
            "legislation_chunk_rows": count_nonempty_lines(REPO_ROOT / "indexes" / "legislation_chunks.jsonl"),
            "jurisprudence_manifest_rows": count_nonempty_lines(REPO_ROOT / "indexes" / "jurisprudence_manifest.jsonl"),
            "jurisprudence_chunk_rows": count_nonempty_lines(REPO_ROOT / "indexes" / "jurisprudence_chunks.jsonl"),
        },
        "documents": {
            "legislation_docs": file_count(REPO_ROOT / "mexico" / "legislation", "*.md"),
            "tesis_docs": file_count(jurisprudence_root / "tesis", "*.json"),
            "precedente_docs": file_count(jurisprudence_root / "precedentes", "*.json"),
            "voto_docs": file_count(jurisprudence_root / "votos", "*.json"),
            "acuerdo_docs": file_count(jurisprudence_root / "acuerdos", "*.json"),
        },
        "recent_documents": newest_files(jurisprudence_root, "*.json", MAX_RECENT_ITEMS),
        "recent_legislation": newest_files(REPO_ROOT / "mexico" / "legislation", "*.md", 5),
    }


def build_dashboard_payload() -> dict[str, Any]:
    return {
        "generated_at": utc_now_iso(),
        "repo_root": str(REPO_ROOT),
        "corpus": corpus_panel(),
        "legislation": legislation_panel(),
        "jurisprudence": jurisprudence_panel(),
        "releases": release_panel(),
    }


def require_api_key() -> None:
    if API_KEY:
        return
    raise RuntimeError("LEXERA_API_KEY is missing from the web service environment.")


def backend_request(method: str, path: str, *, payload: Any | None = None) -> Any:
    require_api_key()
    url = f"{API_BASE_URL}{path}"
    data = None
    headers = {"Authorization": f"Bearer {API_KEY}"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = Request(url=url, data=data, method=method.upper(), headers=headers)
    try:
        with urlopen(request, timeout=120) as response:
            body = response.read()
            if not body:
                return None
            return json.loads(body.decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        detail = body
        try:
            parsed = json.loads(body)
            if isinstance(parsed, dict):
                detail = str(parsed.get("detail") or parsed.get("error") or body)
        except json.JSONDecodeError:
            pass
        raise RuntimeError(f"{exc.code} {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Backend unreachable: {exc.reason}") from exc


def collect_context_snippets(expediente: dict[str, Any]) -> list[dict[str, str]]:
    snippets: list[dict[str, str]] = []
    for document in expediente.get("documents") or []:
        versions = document.get("versions") or []
        current_version = versions[-1] if versions else None
        excerpt = ""
        if current_version:
            excerpt = str(current_version.get("extracted_text") or "")[:1200]
        if not excerpt:
            excerpt = str(document.get("description") or "")[:600]
        if not excerpt:
            continue
        snippets.append(
            {
                "title": str(document.get("title") or "Documento"),
                "document_type": str(document.get("document_type") or "otro"),
                "excerpt": excerpt.strip(),
            }
        )
        total_chars = sum(len(row["excerpt"]) for row in snippets)
        if total_chars >= MAX_CONTEXT_CHARS:
            break
    return snippets


def build_copilot_messages(expediente: dict[str, Any], prompt: str) -> list[dict[str, str]]:
    parties = ", ".join(
        f"{party.get('display_name')} ({party.get('role')})" for party in (expediente.get("parties") or [])[:8]
    ) or "Sin partes registradas"
    snippets = collect_context_snippets(expediente)
    snippet_text = "\n\n".join(
        f"[{row['document_type']}] {row['title']}\n{row['excerpt']}" for row in snippets
    ) or "No hay texto documental extraído todavía."
    system_prompt = (
        "Eres Lexera, un copiloto jurídico para expedientes de derecho mexicano. "
        "Trabaja solo con México. No inventes jurisprudencia, expedientes, autoridades ni citas. "
        "Si falta base documental o normativa, dilo explícitamente. "
        "Responde en español con claridad operativa. "
        "Distingue entre hechos confirmados, huecos de información y sugerencias de siguiente paso. "
        "Antes de entrar al fondo del asunto, revisa siempre cuestiones previas y presupuestos procesales: "
        "personalidad, personeria, poderes, legitimacion, competencia, via, emplazamiento o notificacion, "
        "fechas criticas, plazos y preclusion. "
        "Si alguno de esos puntos no esta acreditado, priorizalo sobre el fondo. "
        "No afirmes que un borrador está listo para liberación final."
    )
    user_prompt = (
        f"Expediente: {expediente.get('title')}\n"
        f"Número: {expediente.get('expediente_number') or 'Sin número'}\n"
        f"Materia: {expediente.get('matter_type')}\n"
        f"Jurisdicción: {expediente.get('jurisdiction_level') or 'No definida'}\n"
        f"Autoridad: {expediente.get('court_or_authority') or 'No capturada'}\n"
        f"Resumen: {expediente.get('summary') or 'Sin resumen'}\n"
        f"Partes: {parties}\n\n"
        f"Fragmentos documentales:\n{snippet_text}\n\n"
        f"Solicitud del usuario:\n{prompt.strip()}\n\n"
        "Devuelve una respuesta útil para trabajo jurídico interno. "
        "Primero responde con control previo y procesal si es relevante. "
        "Si propones un borrador, márcalo como borrador preliminar."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_case_analysis_messages(expediente: dict[str, Any], objective: str) -> list[dict[str, str]]:
    parties = ", ".join(
        f"{party.get('display_name')} ({party.get('role')})" for party in (expediente.get("parties") or [])[:8]
    ) or "Sin partes registradas"
    snippets = collect_context_snippets(expediente)
    snippet_text = "\n\n".join(
        f"[{row['document_type']}] {row['title']}\n{row['excerpt']}" for row in snippets
    ) or "No hay texto documental extraído todavía."
    system_prompt = (
        "Eres Lexera, un analista de expedientes en curso para derecho mexicano. "
        "Tu trabajo es ordenar expedientes ya iniciados. "
        "No inventes hechos, fechas, notificaciones, tribunales, actuaciones ni jurisprudencia. "
        "Distingue expresamente entre hechos confirmados y vacios documentales. "
        "Antes de analizar el fondo, haz un control previo obligatorio de presupuestos procesales y cuestiones previas: "
        "personalidad, personeria, poderes, legitimacion, competencia, via, emplazamiento o notificacion, "
        "fechas criticas, plazos y posibles preclusiones. "
        "Si esos puntos no estan claros, dilo y baja la confianza del analisis de fondo. "
        "Si la informacion es insuficiente para fijar estrategia, dilo. "
        "Responde en español con encabezados claros y enfoque operativo."
    )
    user_prompt = (
        f"Expediente: {expediente.get('title')}\n"
        f"Número: {expediente.get('expediente_number') or 'Sin número'}\n"
        f"Materia: {expediente.get('matter_type')}\n"
        f"Jurisdicción: {expediente.get('jurisdiction_level') or 'No definida'}\n"
        f"Autoridad: {expediente.get('court_or_authority') or 'No capturada'}\n"
        f"Resumen registrado: {expediente.get('summary') or 'Sin resumen'}\n"
        f"Partes: {parties}\n\n"
        f"Fragmentos documentales:\n{snippet_text}\n\n"
        f"Objetivo adicional del usuario:\n{objective.strip() or 'Reconstruir el expediente en curso.'}\n\n"
        "Devuelve exactamente estas secciones:\n"
        "1. Expediente Snapshot\n"
        "2. Control Previo Antes del Fondo\n"
        "3. Que Ha Pasado\n"
        "4. Estado Procesal Actual\n"
        "5. Que Sigue\n"
        "6. Estrategia Preliminar\n"
        "7. Riesgos y Huecos de Informacion\n"
        "8. Siguiente Accion Recomendada\n\n"
        "En 'Control Previo Antes del Fondo' revisa expresamente: personalidad, personeria, poderes, legitimacion, "
        "competencia, via, emplazamiento o notificacion, fechas clave y plazos. "
        "En 'Que Ha Pasado' prioriza cronologia con fechas exactas si existen. "
        "En 'Que Sigue' no inventes plazos; si faltan actos de notificacion o datos del procedimiento, dilo. "
        "En 'Estrategia Preliminar' formula hipotesis condicionadas a la evidencia cargada y no entres al fondo "
        "si el control previo esta roto o incompleto."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def build_synthesis_messages(expediente: dict[str, Any], objective: str) -> list[dict[str, str]]:
    parties = ", ".join(
        f"{party.get('display_name')} ({party.get('role')})" for party in (expediente.get("parties") or [])[:8]
    ) or "Sin partes registradas"
    snippets = collect_context_snippets(expediente)
    snippet_text = "\n\n".join(
        f"[{row['document_type']}] {row['title']}\n{row['excerpt']}" for row in snippets
    ) or "No hay texto documental extraído todavía."
    system_prompt = (
        "Eres Lexera, sintetizador de expedientes de derecho mexicano. "
        "Tu trabajo es construir una sintesis vigente y util del expediente. "
        "No inventes hechos, fechas, notificaciones, tribunales, actuaciones ni jurisprudencia. "
        "Distingue expresamente entre hechos confirmados y vacios documentales. "
        "No entres al fondo del asunto ni formules estrategia de merito. "
        "Tu salida debe servir como base previa y obligatoria para trabajo posterior."
    )
    user_prompt = (
        f"Expediente: {expediente.get('title')}\n"
        f"Número: {expediente.get('expediente_number') or 'Sin número'}\n"
        f"Materia: {expediente.get('matter_type')}\n"
        f"Jurisdicción: {expediente.get('jurisdiction_level') or 'No definida'}\n"
        f"Autoridad: {expediente.get('court_or_authority') or 'No capturada'}\n"
        f"Resumen registrado: {expediente.get('summary') or 'Sin resumen'}\n"
        f"Partes: {parties}\n\n"
        f"Fragmentos documentales:\n{snippet_text}\n\n"
        f"Objetivo adicional del usuario:\n{objective.strip() or 'Generar una sintesis vigente del expediente.'}\n\n"
        "Devuelve exactamente estas secciones:\n"
        "1. Expediente Snapshot\n"
        "2. Hechos Confirmados\n"
        "3. Cronologia Relevante\n"
        "4. Documentos Clave del Expediente\n"
        "5. Control Previo Antes del Fondo\n"
        "6. Huecos de Informacion\n"
        "7. Siguiente Paso Operativo\n\n"
        "No incluyas estrategia de fondo ni analisis de merito. "
        "En control previo revisa personalidad, personeria, poderes, legitimacion, competencia, via, "
        "emplazamiento o notificacion, fechas criticas y plazos."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def get_synthesis_state(expediente: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    extra = expediente.get("extra")
    if not isinstance(extra, dict):
        return "missing", None
    synthesis = extra.get("latest_synthesis")
    if not isinstance(synthesis, dict):
        return "missing", None
    status = str(extra.get("synthesis_status") or "current").strip() or "current"
    return status, synthesis


def get_draft_section_spec(section_key: str) -> dict[str, str]:
    section = DRAFT_SECTION_SPECS.get(str(section_key or "").strip())
    if section is not None:
        return {"key": str(section_key).strip(), **section}
    return {
        "key": "otra_seccion",
        "label": "Otra seccion",
        "guidance": "Redacta solo la seccion pedida, sin convertirla en un escrito completo.",
    }


def find_section_document(
    expediente: dict[str, Any], *, bundle_title: str, section_key: str, document_type: str
) -> dict[str, Any] | None:
    normalized_bundle = bundle_title.strip().lower()
    normalized_section = section_key.strip().lower()
    normalized_type = document_type.strip().lower()
    for document in expediente.get("documents") or []:
        extra = document.get("extra") if isinstance(document.get("extra"), dict) else {}
        if (
            str(extra.get("draft_bundle_title") or "").strip().lower() == normalized_bundle
            and str(extra.get("draft_section_key") or "").strip().lower() == normalized_section
            and str(document.get("document_type") or "").strip().lower() == normalized_type
        ):
            return document
    return None


def find_document_version(expediente: dict[str, Any], version_id: str) -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, None]:
    normalized_version_id = str(version_id or "").strip()
    for document in expediente.get("documents") or []:
        for version in document.get("versions") or []:
            if str(version.get("id") or "") == normalized_version_id:
                return document, version
    return None, None


def has_approved_receipt_for_version(expediente: dict[str, Any], version_id: str) -> bool:
    normalized_version_id = str(version_id or "").strip()
    for receipt in expediente.get("release_receipts") or []:
        if (
            str(receipt.get("document_version_id") or "") == normalized_version_id
            and str(receipt.get("verdict") or "").strip().lower() == "approved"
            and bool(receipt.get("execution_id"))
        ):
            return True
    return False


def build_section_draft_messages(
    expediente: dict[str, Any],
    *,
    bundle_title: str,
    section_key: str,
    document_type: str,
    prompt: str,
    synthesis: dict[str, Any],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    section = get_draft_section_spec(section_key)
    parties = ", ".join(
        f"{party.get('display_name')} ({party.get('role')})" for party in (expediente.get("parties") or [])[:8]
    ) or "Sin partes registradas"
    snippets = collect_context_snippets(expediente)
    snippet_text = "\n\n".join(
        f"[{row['document_type']}] {row['title']}\n{row['excerpt']}" for row in snippets
    ) or "No hay texto documental extraido todavia."
    checklist = expediente.get("extra", {}).get("pre_merits_checklist")
    checklist_summary = "Sin checklist estructurado todavia."
    if isinstance(checklist, dict):
        summary_status = str(checklist.get("summary_status") or "dudoso")
        summary_note = str(checklist.get("summary_note") or "Sin nota general.")
        checklist_summary = f"{summary_status}: {summary_note}"
    synthesis_text = str(synthesis.get("content") or "").strip() or "Sin sintesis disponible."
    system_prompt = (
        "Eres Lexera, redactor juridico por secciones para expedientes de derecho mexicano. "
        "No redactes el escrito completo. Trabaja solo la seccion solicitada. "
        "No inventes jurisprudencia, hechos, fechas, notificaciones, autoridades ni citas. "
        "Debes apoyar la redaccion en la sintesis vigente y en los documentos cargados del expediente. "
        "Antes del fondo, respeta las cuestiones previas y presupuestos procesales. "
        "Devuelve exactamente estas secciones y en este orden:\n"
        "1. Base Documental Usada\n"
        "2. Huecos y Supuestos\n"
        "3. Nivel de Confianza\n"
        "4. Borrador de la Seccion\n\n"
        "En 'Base Documental Usada' identifica solo la evidencia realmente utilizada. "
        "En 'Huecos y Supuestos' di que falta o que quedo condicionado. "
        "En 'Nivel de Confianza' usa una sola etiqueta: alto, medio o bajo, con una breve explicacion. "
        "En 'Borrador de la Seccion' entrega texto util para trabajo interno, nunca marques que ya esta listo para firma."
    )
    user_prompt = (
        f"Expediente: {expediente.get('title')}\n"
        f"Numero: {expediente.get('expediente_number') or 'Sin numero'}\n"
        f"Tipo de documento: {document_type}\n"
        f"Escrito o bundle de trabajo: {bundle_title}\n"
        f"Seccion solicitada: {section['label']}\n"
        f"Guia de la seccion: {section['guidance']}\n"
        f"Materia: {expediente.get('matter_type')}\n"
        f"Jurisdiccion: {expediente.get('jurisdiction_level') or 'No definida'}\n"
        f"Autoridad: {expediente.get('court_or_authority') or 'No capturada'}\n"
        f"Partes: {parties}\n"
        f"Resumen del checklist previo: {checklist_summary}\n\n"
        f"Sintesis vigente:\n{synthesis_text}\n\n"
        f"Fragmentos documentales:\n{snippet_text}\n\n"
        f"Instruccion adicional del usuario:\n{prompt.strip()}\n\n"
        "Redacta unicamente la seccion pedida. "
        "Si la seccion depende de extremos no acreditados, dilo claramente en huecos y baja la confianza."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ], snippets


def build_revision_messages(
    expediente: dict[str, Any],
    *,
    document: dict[str, Any],
    version: dict[str, Any],
    revision_mode: str,
    objective: str,
    synthesis: dict[str, Any],
) -> list[dict[str, str]]:
    mode = "broad" if revision_mode == "broad" else "narrow"
    parties = ", ".join(
        f"{party.get('display_name')} ({party.get('role')})" for party in (expediente.get("parties") or [])[:8]
    ) or "Sin partes registradas"
    snippets = collect_context_snippets(expediente)
    snippet_text = "\n\n".join(
        f"[{row['document_type']}] {row['title']}\n{row['excerpt']}" for row in snippets
    ) or "No hay texto documental extraido todavia."
    current_text = str(version.get("extracted_text") or "").strip()
    checklist = expediente.get("extra", {}).get("pre_merits_checklist")
    checklist_summary = "Sin checklist estructurado todavia."
    if isinstance(checklist, dict):
        checklist_summary = (
            f"{str(checklist.get('summary_status') or 'dudoso')}: "
            f"{str(checklist.get('summary_note') or 'Sin nota general.')}"
        )
    system_prompt = (
        "Eres Lexera, revisor juridico de texto para expedientes de derecho mexicano. "
        "Debes devolver solo JSON valido, sin markdown y sin texto adicional. "
        "No inventes hechos, fechas, jurisprudencia, autoridades ni citas. "
        "Si el modo es narrow, limita los cambios a correcciones puntuales y conservadoras. "
        "Si el modo es broad, puedes reordenar o reescribir ampliamente, pero solo dentro del texto entregado. "
        "Tu JSON debe tener exactamente esta forma:\n"
        "{\n"
        '  "change_scope": "narrow|broad",\n'
        '  "confidence": "alto|medio|bajo",\n'
        '  "justification": ["motivo 1", "motivo 2"],\n'
        '  "revised_text": "texto completo revisado"\n'
        "}\n"
        "En narrow no reescribas el documento completo si no es necesario. "
        "Mantente dentro del expediente y del texto base."
    )
    user_prompt = (
        f"Expediente: {expediente.get('title')}\n"
        f"Numero: {expediente.get('expediente_number') or 'Sin numero'}\n"
        f"Documento: {document.get('title')}\n"
        f"Tipo de documento: {document.get('document_type')}\n"
        f"Version base: {version.get('version_number')}\n"
        f"Modo de revision: {mode}\n"
        f"Resumen checklist previo: {checklist_summary}\n"
        f"Partes: {parties}\n\n"
        f"Sintesis vigente:\n{str(synthesis.get('content') or '').strip() or 'Sin sintesis disponible.'}\n\n"
        f"Texto actual a revisar:\n{current_text}\n\n"
        f"Contexto documental adicional:\n{snippet_text}\n\n"
        f"Instruccion del usuario:\n{objective.strip()}\n\n"
        "Corrige o mejora el texto segun el modo pedido. "
        "Si detectas que el control previo esta incompleto, refleja eso en la justificacion y evita exagerar el texto."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def normalize_revision_payload(raw: dict[str, Any], *, current_text: str, requested_mode: str) -> dict[str, Any]:
    allowed_scopes = {"narrow", "broad"}
    allowed_confidence = {"alto", "medio", "bajo"}
    change_scope = str(raw.get("change_scope") or requested_mode or "narrow").strip().lower()
    if change_scope not in allowed_scopes:
        change_scope = "narrow"
    confidence = str(raw.get("confidence") or "medio").strip().lower()
    if confidence not in allowed_confidence:
        confidence = "medio"
    justification = raw.get("justification")
    if not isinstance(justification, list):
        justification = [str(justification or "").strip()] if str(justification or "").strip() else []
    cleaned_justification = [str(item).strip() for item in justification if str(item).strip()]
    revised_text = str(raw.get("revised_text") or "").strip()
    if not revised_text:
        revised_text = current_text
    diff_lines = list(
        difflib.unified_diff(
            current_text.splitlines(),
            revised_text.splitlines(),
            fromfile="version_actual",
            tofile="version_revisada",
            lineterm="",
        )
    )
    return {
        "change_scope": change_scope,
        "confidence": confidence,
        "justification": cleaned_justification,
        "revised_text": revised_text,
        "diff_text": "\n".join(diff_lines),
        "changed": revised_text != current_text,
    }


def build_defendability_messages(
    expediente: dict[str, Any],
    *,
    document: dict[str, Any],
    version: dict[str, Any],
    synthesis: dict[str, Any],
) -> list[dict[str, str]]:
    parties = ", ".join(
        f"{party.get('display_name')} ({party.get('role')})" for party in (expediente.get("parties") or [])[:8]
    ) or "Sin partes registradas"
    snippets = collect_context_snippets(expediente)
    snippet_text = "\n\n".join(
        f"[{row['document_type']}] {row['title']}\n{row['excerpt']}" for row in snippets
    ) or "No hay texto documental extraido todavia."
    current_text = str(version.get("extracted_text") or "").strip()
    system_prompt = (
        "Eres Lexera, evaluador de defendibilidad para expedientes de derecho mexicano. "
        "Debes devolver solo JSON valido, sin markdown ni texto adicional. "
        "No inventes evidencia, citas, jurisprudencia ni actuaciones. "
        "Evalua si el texto puede defenderse con base en el expediente cargado. "
        "Usa solo estos estatus de soporte: acreditado, inferido, no_acreditado. "
        "Devuelve exactamente esta forma:\n"
        "{\n"
        '  "summary_status": "defendable|review_required|blocked",\n'
        '  "summary_note": "texto breve",\n'
        '  "items": [\n'
        "    {\n"
        '      "claim": "punto concreto del texto",\n'
        '      "support_status": "acreditado|inferido|no_acreditado",\n'
        '      "evidence_basis": "que evidencia sostiene este punto",\n'
        '      "expediente_support": "que parte del expediente lo acredita",\n'
        '      "missing_for_court": "que falta para sostenerlo ante un juez"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "Maximo 5 items y solo sobre puntos verdaderamente relevantes del texto."
    )
    user_prompt = (
        f"Expediente: {expediente.get('title')}\n"
        f"Numero: {expediente.get('expediente_number') or 'Sin numero'}\n"
        f"Documento: {document.get('title')}\n"
        f"Tipo de documento: {document.get('document_type')}\n"
        f"Version: {version.get('version_number')}\n"
        f"Partes: {parties}\n\n"
        f"Sintesis vigente:\n{str(synthesis.get('content') or '').strip() or 'Sin sintesis disponible.'}\n\n"
        f"Texto a evaluar:\n{current_text}\n\n"
        f"Contexto documental adicional:\n{snippet_text}\n\n"
        "Responde a estas tres preguntas para cada item:\n"
        "1. Que evidencia sostiene este punto\n"
        "2. Que parte del expediente lo acredita\n"
        "3. Que falta para sostenerlo ante un juez\n\n"
        "Si el expediente no acredita un punto, usa no_acreditado. "
        "Si solo es una inferencia razonable pero no acreditada, usa inferido."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def normalize_defendability_gate(expediente: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    allowed_summary = {"defendable", "review_required", "blocked"}
    allowed_support = {"acreditado", "inferido", "no_acreditado"}
    items = []
    for item in raw.get("items") or []:
        if not isinstance(item, dict):
            continue
        support_status = str(item.get("support_status") or "inferido").strip().lower()
        if support_status not in allowed_support:
            support_status = "inferido"
        items.append(
            {
                "claim": str(item.get("claim") or "").strip(),
                "support_status": support_status,
                "evidence_basis": str(item.get("evidence_basis") or "").strip(),
                "expediente_support": str(item.get("expediente_support") or "").strip(),
                "missing_for_court": str(item.get("missing_for_court") or "").strip(),
            }
        )
    checklist = expediente.get("extra", {}).get("pre_merits_checklist")
    blocking_reasons: list[str] = []
    checklist_snapshot: list[dict[str, str]] = []
    if isinstance(checklist, dict):
        critical_required = {"personalidad", "personeria", "poderes", "legitimacion"}
        critical_strict = {"emplazamiento_notificacion", "plazos_preclusion"}
        for item in checklist.get("items") or []:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip()
            status = str(item.get("status") or "").strip().lower()
            checklist_snapshot.append({"key": key, "status": status})
            if key in critical_required and status != "acreditado":
                blocking_reasons.append(f"{key}:{status}")
            if key in critical_strict and status in {"dudoso", "faltante"}:
                blocking_reasons.append(f"{key}:{status}")
    no_support_count = sum(1 for item in items if item["support_status"] == "no_acreditado")
    inferred_count = sum(1 for item in items if item["support_status"] == "inferido")
    summary_status = str(raw.get("summary_status") or "review_required").strip().lower()
    if summary_status not in allowed_summary:
        summary_status = "review_required"
    if blocking_reasons or no_support_count:
        summary_status = "blocked"
    elif inferred_count and summary_status == "defendable":
        summary_status = "review_required"
    summary_note = str(raw.get("summary_note") or "").strip()
    if blocking_reasons and not summary_note:
        summary_note = "El texto no es liberable por faltas procesales o de sustento acreditado."
    return {
        "summary_status": summary_status,
        "summary_note": summary_note,
        "items": items[:5],
        "blocking_reasons": blocking_reasons,
        "checklist_snapshot": checklist_snapshot,
        "generated_at": utc_now_iso(),
        "model": OLLAMA_MODEL,
    }


def build_preflight_checklist_messages(expediente: dict[str, Any], objective: str) -> list[dict[str, str]]:
    parties = ", ".join(
        f"{party.get('display_name')} ({party.get('role')})" for party in (expediente.get("parties") or [])[:8]
    ) or "Sin partes registradas"
    snippets = collect_context_snippets(expediente)
    snippet_text = "\n\n".join(
        f"[{row['document_type']}] {row['title']}\n{row['excerpt']}" for row in snippets
    ) or "No hay texto documental extraído todavía."
    system_prompt = (
        "Eres Lexera, auditor previo de expedientes de derecho mexicano. "
        "Debes devolver solo JSON valido, sin markdown y sin texto adicional. "
        "No inventes hechos, fechas, poderes, notificaciones ni conclusiones. "
        "Evalua exclusivamente con base en el expediente cargado. "
        "Usa solo estos estatus: acreditado, dudoso, faltante. "
        "Si la evidencia es parcial o contradictoria, usa dudoso."
    )
    user_prompt = (
        f"Expediente: {expediente.get('title')}\n"
        f"Número: {expediente.get('expediente_number') or 'Sin número'}\n"
        f"Materia: {expediente.get('matter_type')}\n"
        f"Jurisdicción: {expediente.get('jurisdiction_level') or 'No definida'}\n"
        f"Autoridad: {expediente.get('court_or_authority') or 'No capturada'}\n"
        f"Partes: {parties}\n"
        f"Objetivo adicional: {objective.strip() or 'Auditar control previo antes del fondo.'}\n\n"
        f"Fragmentos documentales:\n{snippet_text}\n\n"
        "Devuelve un JSON con esta forma exacta:\n"
        "{\n"
        '  "summary_status": "acreditado|dudoso|faltante",\n'
        '  "summary_note": "texto breve",\n'
        '  "items": [\n'
        "    {\n"
        '      "key": "personalidad",\n'
        '      "label": "Personalidad",\n'
        '      "status": "acreditado|dudoso|faltante",\n'
        '      "evidence": "texto breve",\n'
        '      "risk": "texto breve",\n'
        '      "next_action": "texto breve"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "Los items deben ser exactamente estos y en este orden: "
        "personalidad, personeria, poderes, legitimacion, competencia, via, emplazamiento_notificacion, fechas_clave, plazos_preclusion."
    )
    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    fenced_start = text.find("```json")
    if fenced_start != -1:
        fenced_end = text.find("```", fenced_start + 7)
        if fenced_end != -1:
            text = text[fenced_start + 7 : fenced_end].strip()
    elif "```" in text:
        first = text.find("```")
        second = text.find("```", first + 3)
        if second != -1:
            text = text[first + 3 : second].strip()

    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            value, _next_index = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("Model did not return a valid JSON object.")


def normalize_preflight_checklist(raw: dict[str, Any]) -> dict[str, Any]:
    allowed_statuses = {"acreditado", "dudoso", "faltante"}
    ordered_keys = [
        ("personalidad", "Personalidad"),
        ("personeria", "Personeria"),
        ("poderes", "Poderes"),
        ("legitimacion", "Legitimacion"),
        ("competencia", "Competencia"),
        ("via", "Via"),
        ("emplazamiento_notificacion", "Emplazamiento / Notificacion"),
        ("fechas_clave", "Fechas clave"),
        ("plazos_preclusion", "Plazos y preclusion"),
    ]
    by_key = {}
    for item in raw.get("items") or []:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if key:
            by_key[key] = item

    items: list[dict[str, Any]] = []
    summary_status = str(raw.get("summary_status") or "dudoso").strip().lower()
    if summary_status not in allowed_statuses:
        summary_status = "dudoso"

    for key, label in ordered_keys:
        item = by_key.get(key) or {}
        status = str(item.get("status") or "faltante").strip().lower()
        if status not in allowed_statuses:
            status = "faltante"
        items.append(
            {
                "key": key,
                "label": label,
                "status": status,
                "evidence": str(item.get("evidence") or "").strip(),
                "risk": str(item.get("risk") or "").strip(),
                "next_action": str(item.get("next_action") or "").strip(),
            }
        )

    return {
        "summary_status": summary_status,
        "summary_note": str(raw.get("summary_note") or "").strip(),
        "items": items,
        "generated_at": utc_now_iso(),
        "generator": "lexera_preflight_checklist",
        "model": OLLAMA_MODEL,
    }


def run_ollama_chat(messages: list[dict[str, str]]) -> dict[str, Any]:
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "messages": messages,
        "options": {"temperature": 0.2},
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        url=OLLAMA_CHAT_URL,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=240) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Ollama HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Ollama unreachable: {exc.reason}") from exc


def path_segments(path: str) -> list[str]:
    return [segment for segment in path.split("/") if segment]


class OperatorConsoleHandler(BaseHTTPRequestHandler):
    server_version = "lexera-web/0.2"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/ops/api/dashboard":
            self.write_json(build_dashboard_payload())
            return
        if parsed.path == "/api/ping":
            self.write_json({"ok": True, "generated_at": utc_now_iso()})
            return
        if parsed.path == "/app-api/bootstrap":
            self.handle_workspace_bootstrap()
            return
        if parsed.path == "/app-api/agenda":
            self.handle_workspace_agenda()
            return
        segments = path_segments(parsed.path)
        if parsed.path == "/app-api/expedientes":
            self.handle_proxy_json("GET", "/expedientes")
            return
        if len(segments) == 3 and segments[:2] == ["app-api", "expedientes"]:
            self.handle_workspace_detail(segments[2])
            return
        if len(segments) >= 4 and segments[:2] == ["app-api", "expedientes"]:
            expediente_path = "/" + "/".join(segments[1:])
            self.handle_proxy_json("GET", expediente_path)
            return
        self.serve_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        segments = path_segments(parsed.path)
        if parsed.path == "/app-api/expedientes":
            self.handle_proxy_json("POST", "/expedientes", payload=self.read_json_body())
            return
        if len(segments) == 4 and segments[:2] == ["app-api", "expedientes"] and segments[3] == "documents":
            path = "/" + "/".join(segments[1:])
            self.handle_proxy_json("POST", path, payload=self.read_json_body())
            return
        if len(segments) == 4 and segments[:2] == ["app-api", "expedientes"] and segments[3] == "events":
            path = "/" + "/".join(segments[1:])
            self.handle_proxy_json("POST", path, payload=self.read_json_body())
            return
        if len(segments) == 4 and segments[:2] == ["app-api", "expedientes"] and segments[3] == "deadlines":
            path = "/" + "/".join(segments[1:])
            self.handle_proxy_json("POST", path, payload=self.read_json_body())
            return
        if len(segments) == 4 and segments[:2] == ["app-api", "expedientes"] and segments[3] == "release":
            self.handle_workspace_release(segments[2])
            return
        if len(segments) == 4 and segments[:2] == ["app-api", "expedientes"] and segments[3] == "drafts":
            self.handle_workspace_draft(segments[2])
            return
        if len(segments) == 4 and segments[:2] == ["app-api", "expedientes"] and segments[3] == "revisions":
            self.handle_workspace_revision(segments[2])
            return
        if len(segments) == 4 and segments[:2] == ["app-api", "expedientes"] and segments[3] == "defendability-gate":
            self.handle_workspace_defendability_gate(segments[2])
            return
        if len(segments) == 4 and segments[:2] == ["app-api", "expedientes"] and segments[3] == "analysis":
            self.handle_workspace_case_analysis(segments[2])
            return
        if len(segments) == 4 and segments[:2] == ["app-api", "expedientes"] and segments[3] == "preflight-checklist":
            self.handle_workspace_preflight_checklist(segments[2])
            return
        if len(segments) == 4 and segments[:2] == ["app-api", "expedientes"] and segments[3] == "copilot":
            expediente_id = segments[2]
            self.handle_copilot(expediente_id)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        segments = path_segments(parsed.path)
        if (
            len(segments) == 5
            and segments[:2] == ["app-api", "expedientes"]
            and segments[3] == "deadlines"
        ):
            path = "/" + "/".join(segments[1:])
            self.handle_proxy_json("PATCH", path, payload=self.read_json_body())
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_HEAD(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path in {"/api/ping", "/ops/api/dashboard"}:
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        self.serve_static(parsed.path, head_only=True)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length") or "0")
        raw = self.rfile.read(content_length) if content_length else b"{}"
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON body.") from exc
        if not isinstance(parsed, dict):
            raise ValueError("JSON body must be an object.")
        return parsed

    def write_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def write_error_json(self, detail: str, status: HTTPStatus = HTTPStatus.BAD_REQUEST) -> None:
        self.write_json({"error": detail}, status=status)

    def handle_workspace_bootstrap(self) -> None:
        try:
            items = backend_request("GET", "/expedientes?limit=200")
            agenda = backend_request("GET", "/expedientes/agenda/calendar")
            procedural_tracks = backend_request("GET", "/expedientes/meta/procedural-deadline-tracks")
        except RuntimeError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.SERVICE_UNAVAILABLE)
            return
        self.write_json(
            {
                "items": items or [],
                "agenda": (agenda or {}).get("items") or [],
                "procedural_tracks": (procedural_tracks or {}).get("items") or [],
                "draft_sections": [
                    {"key": key, **value} for key, value in DRAFT_SECTION_SPECS.items()
                ],
                "generated_at": utc_now_iso(),
            }
        )

    def handle_workspace_agenda(self) -> None:
        try:
            agenda = backend_request("GET", "/expedientes/agenda/calendar")
        except RuntimeError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_GATEWAY)
            return
        self.write_json(agenda or {"items": [], "generated_at": utc_now_iso()})

    def handle_workspace_detail(self, expediente_id: str) -> None:
        try:
            expediente = backend_request("GET", f"/expedientes/{expediente_id}")
            receipts = backend_request("GET", f"/expedientes/{expediente_id}/release-receipts")
        except RuntimeError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_GATEWAY)
            return
        if isinstance(receipts, dict):
            expediente["release_receipts"] = receipts.get("items") or []
        else:
            expediente["release_receipts"] = []
        self.write_json(expediente)

    def handle_proxy_json(self, method: str, backend_path: str, payload: dict[str, Any] | None = None) -> None:
        try:
            response = backend_request(method, backend_path, payload=payload)
        except ValueError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
            return
        except RuntimeError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_GATEWAY)
            return
        self.write_json(response if response is not None else {"ok": True})

    def handle_copilot(self, expediente_id: str) -> None:
        try:
            payload = self.read_json_body()
        except ValueError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        prompt = str(payload.get("prompt") or "").strip()
        if not prompt:
            self.write_error_json("Prompt is required.", status=HTTPStatus.UNPROCESSABLE_ENTITY)
            return

        try:
            expediente = backend_request("GET", f"/expedientes/{expediente_id}")
            messages = build_copilot_messages(expediente, prompt)
            ollama_response = run_ollama_chat(messages)
        except RuntimeError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_GATEWAY)
            return

        answer = (
            ollama_response.get("message", {}).get("content")
            if isinstance(ollama_response, dict)
            else None
        )
        self.write_json(
            {
                "expediente_id": expediente_id,
                "model": OLLAMA_MODEL,
                "answer": str(answer or "No hubo respuesta del modelo.").strip(),
                "context_documents": [
                    {"title": row["title"], "document_type": row["document_type"]}
                    for row in collect_context_snippets(expediente)
                ],
                "generated_at": utc_now_iso(),
            }
        )

    def handle_workspace_draft(self, expediente_id: str) -> None:
        try:
            payload = self.read_json_body()
        except ValueError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        prompt = str(payload.get("prompt") or "").strip()
        bundle_title = str(payload.get("bundle_title") or payload.get("title") or "").strip()
        document_type = str(payload.get("document_type") or "escrito").strip()
        section_key = str(payload.get("section_key") or "").strip()
        if not prompt or not bundle_title or not section_key:
            self.write_error_json(
                "bundle_title, section_key and prompt are required.",
                status=HTTPStatus.UNPROCESSABLE_ENTITY,
            )
            return

        try:
            expediente = backend_request("GET", f"/expedientes/{expediente_id}")
            synthesis_status, synthesis = get_synthesis_state(expediente)
            if synthesis_status != "current" or synthesis is None:
                self.write_error_json(
                    "Genera primero una sintesis vigente del expediente antes de redactar borradores.",
                    status=HTTPStatus.PRECONDITION_FAILED,
                )
                return
            section = get_draft_section_spec(section_key)
            document_title = f"{bundle_title} - {section['label']}"
            messages, snippets = build_section_draft_messages(
                expediente,
                bundle_title=bundle_title,
                section_key=section_key,
                document_type=document_type,
                prompt=prompt,
                synthesis=synthesis,
            )
            ollama_response = run_ollama_chat(messages)
            answer = str(ollama_response.get("message", {}).get("content") or "").strip()
            encoded = base64.b64encode(answer.encode("utf-8")).decode("ascii")
            version_payload = {
                "source_kind": "generated",
                "file_name": f"{document_title}.md",
                "mime_type": "text/markdown",
                "content_base64": encoded,
                "notes": f"Seccion generada por Lexera: {section['label']}",
                "extracted_text": answer,
                "created_by": "Lexera section drafting engine",
                "extra": {
                    "draft_bundle_title": bundle_title,
                    "draft_section_key": section["key"],
                    "draft_section_label": section["label"],
                    "prompt": prompt,
                    "model": OLLAMA_MODEL,
                    "generated_at": utc_now_iso(),
                    "based_on_synthesis_generated_at": synthesis.get("generated_at"),
                    "context_documents": [
                        {"title": row["title"], "document_type": row["document_type"]}
                        for row in snippets
                    ],
                },
            }
            document_extra = {
                "draft_bundle_title": bundle_title,
                "draft_section_key": section["key"],
                "draft_section_label": section["label"],
                "draft_flow": "sectional",
            }
            existing_document = find_section_document(
                expediente,
                bundle_title=bundle_title,
                section_key=section["key"],
                document_type=document_type,
            )
            if existing_document is None:
                created = backend_request(
                    "POST",
                    f"/expedientes/{expediente_id}/documents",
                    payload={
                        "document": {
                            "title": document_title,
                            "document_type": document_type,
                            "description": str(payload.get("description") or "").strip()
                            or f"Seccion {section['label']} generada desde Lexera",
                            "event_date": payload.get("event_date") or None,
                            "extra": document_extra,
                        },
                        "version": version_payload,
                    },
                )
                created_document = None
                for document in reversed(created.get("documents") or []):
                    if str(document.get("title") or "") == document_title and (
                        str((document.get("extra") or {}).get("draft_section_key") or "") == section["key"]
                    ):
                        created_document = document
                        break
                document_action = "created"
            else:
                merged_extra = existing_document.get("extra") if isinstance(existing_document.get("extra"), dict) else {}
                created_document = backend_request(
                    "PATCH",
                    f"/expedientes/{expediente_id}/documents/{existing_document['id']}",
                    payload={
                        "title": document_title,
                        "description": str(payload.get("description") or "").strip()
                        or existing_document.get("description")
                        or f"Seccion {section['label']} generada desde Lexera",
                        "event_date": payload.get("event_date") or existing_document.get("event_date"),
                        "extra": {
                            **merged_extra,
                            **document_extra,
                        },
                    },
                )
                backend_request(
                    "POST",
                    f"/expedientes/{expediente_id}/documents/{existing_document['id']}/versions",
                    payload=version_payload,
                )
                created_document = backend_request(
                    "GET",
                    f"/expedientes/{expediente_id}/documents/{existing_document['id']}",
                )
                document_action = "new_version"
        except RuntimeError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_GATEWAY)
            return

        self.write_json(
            {
                "expediente_id": expediente_id,
                "model": OLLAMA_MODEL,
                "answer": answer,
                "bundle_title": bundle_title,
                "section_key": section["key"],
                "section_label": section["label"],
                "document_action": document_action,
                "document": created_document,
                "generated_at": utc_now_iso(),
            },
            status=HTTPStatus.CREATED,
        )

    def handle_workspace_revision(self, expediente_id: str) -> None:
        try:
            payload = self.read_json_body()
        except ValueError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        document_version_id = str(payload.get("document_version_id") or "").strip()
        revision_mode = str(payload.get("revision_mode") or "narrow").strip().lower()
        objective = str(payload.get("objective") or "").strip()
        if not document_version_id or not objective:
            self.write_error_json(
                "document_version_id and objective are required.",
                status=HTTPStatus.UNPROCESSABLE_ENTITY,
            )
            return
        if revision_mode not in {"narrow", "broad"}:
            revision_mode = "narrow"

        try:
            expediente = backend_request("GET", f"/expedientes/{expediente_id}")
            receipts = backend_request("GET", f"/expedientes/{expediente_id}/release-receipts")
            if isinstance(receipts, dict):
                expediente["release_receipts"] = receipts.get("items") or []
            document, version = find_document_version(expediente, document_version_id)
            if document is None or version is None:
                self.write_error_json("La version seleccionada no pertenece al expediente.", status=HTTPStatus.NOT_FOUND)
                return
            synthesis_status, synthesis = get_synthesis_state(expediente)
            if synthesis_status != "current" or synthesis is None:
                self.write_error_json(
                    "Genera primero una sintesis vigente del expediente antes de revisar textos.",
                    status=HTTPStatus.PRECONDITION_FAILED,
                )
                return
            current_text = str(version.get("extracted_text") or "").strip()
            if not current_text:
                self.write_error_json(
                    "La version seleccionada no tiene texto extraido para revision.",
                    status=HTTPStatus.UNPROCESSABLE_ENTITY,
                )
                return
            if revision_mode == "broad" and has_approved_receipt_for_version(expediente, document_version_id):
                self.write_error_json(
                    "La reescritura amplia esta bloqueada para versiones ya aprobadas. Usa revision puntual.",
                    status=HTTPStatus.CONFLICT,
                )
                return
            messages = build_revision_messages(
                expediente,
                document=document,
                version=version,
                revision_mode=revision_mode,
                objective=objective,
                synthesis=synthesis,
            )
            ollama_response = run_ollama_chat(messages)
            raw_answer = str(ollama_response.get("message", {}).get("content") or "").strip()
            parsed = extract_json_object(raw_answer)
            revision = normalize_revision_payload(parsed, current_text=current_text, requested_mode=revision_mode)
            encoded = base64.b64encode(revision["revised_text"].encode("utf-8")).decode("ascii")
            created_version = backend_request(
                "POST",
                f"/expedientes/{expediente_id}/documents/{document['id']}/versions",
                payload={
                    "source_kind": "generated",
                    "file_name": version.get("file_name") or f"{document.get('title')}.md",
                    "mime_type": version.get("mime_type") or "text/markdown",
                    "content_base64": encoded,
                    "notes": f"Revision {revision['change_scope']} generada desde Lexera",
                    "extracted_text": revision["revised_text"],
                    "created_by": "Lexera revision guard",
                    "extra": {
                        "review_guard": True,
                        "revision_mode": revision["change_scope"],
                        "revision_confidence": revision["confidence"],
                        "base_version_id": document_version_id,
                        "base_version_number": version.get("version_number"),
                        "objective": objective,
                        "justification": revision["justification"],
                        "diff_text": revision["diff_text"],
                        "changed": revision["changed"],
                        "model": OLLAMA_MODEL,
                        "generated_at": utc_now_iso(),
                    },
                },
            )
        except RuntimeError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_GATEWAY)
            return
        except ValueError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_GATEWAY)
            return

        self.write_json(
            {
                "expediente_id": expediente_id,
                "document_id": document["id"],
                "document_version_id": created_version.get("id"),
                "base_version_id": document_version_id,
                "revision_mode": revision["change_scope"],
                "confidence": revision["confidence"],
                "justification": revision["justification"],
                "diff_text": revision["diff_text"],
                "changed": revision["changed"],
                "revised_text": revision["revised_text"],
                "version": created_version,
                "model": OLLAMA_MODEL,
                "generated_at": utc_now_iso(),
            },
            status=HTTPStatus.CREATED,
        )

    def handle_workspace_case_analysis(self, expediente_id: str) -> None:
        try:
            payload = self.read_json_body()
        except ValueError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        objective = str(payload.get("objective") or "").strip()
        title = str(payload.get("title") or "").strip() or "Sintesis vigente del expediente"

        try:
            expediente = backend_request("GET", f"/expedientes/{expediente_id}")
            messages = build_synthesis_messages(expediente, objective)
            ollama_response = run_ollama_chat(messages)
            synthesis_text = str(ollama_response.get("message", {}).get("content") or "").strip()
            encoded = base64.b64encode(synthesis_text.encode("utf-8")).decode("ascii")
            created = backend_request(
                "POST",
                f"/expedientes/{expediente_id}/documents",
                payload={
                    "document": {
                        "title": title,
                        "document_type": "constancia",
                        "description": "Sintesis vigente del expediente generada desde Lexera",
                    },
                    "version": {
                        "source_kind": "generated",
                        "file_name": f"{title}.md",
                        "mime_type": "text/markdown",
                        "content_base64": encoded,
                        "notes": "Sintesis vigente del expediente generada por Lexera",
                        "extracted_text": synthesis_text,
                        "created_by": "Lexera synthesis engine",
                        "extra": {
                            "analysis_type": "expediente_synthesis",
                            "objective": objective,
                            "model": OLLAMA_MODEL,
                            "generated_at": utc_now_iso(),
                        },
                    },
                },
            )
            current_extra = expediente.get("extra") if isinstance(expediente.get("extra"), dict) else {}
            latest_synthesis = {
                "title": title,
                "content": synthesis_text,
                "generated_at": utc_now_iso(),
                "model": OLLAMA_MODEL,
                "objective": objective,
                "document_count": len(expediente.get("documents") or []),
            }
            backend_request(
                "PATCH",
                f"/expedientes/{expediente_id}",
                payload={
                    "extra": {
                        **current_extra,
                        "synthesis_status": "current",
                        "latest_synthesis": latest_synthesis,
                    }
                },
            )
        except RuntimeError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_GATEWAY)
            return

        created_document = None
        for document in reversed(created.get("documents") or []):
            if str(document.get("title") or "") == title:
                created_document = document
                break

        self.write_json(
            {
                "expediente_id": expediente_id,
                "model": OLLAMA_MODEL,
                "analysis": synthesis_text,
                "synthesis": latest_synthesis,
                "document": created_document,
                "generated_at": utc_now_iso(),
            },
            status=HTTPStatus.CREATED,
        )

    def handle_workspace_defendability_gate(self, expediente_id: str) -> None:
        try:
            payload = self.read_json_body()
        except ValueError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        document_version_id = str(payload.get("document_version_id") or "").strip()
        if not document_version_id:
            self.write_error_json("document_version_id is required.", status=HTTPStatus.UNPROCESSABLE_ENTITY)
            return

        try:
            expediente = backend_request("GET", f"/expedientes/{expediente_id}")
            receipts = backend_request("GET", f"/expedientes/{expediente_id}/release-receipts")
            if isinstance(receipts, dict):
                expediente["release_receipts"] = receipts.get("items") or []
            document, version = find_document_version(expediente, document_version_id)
            if document is None or version is None:
                self.write_error_json("La version seleccionada no pertenece al expediente.", status=HTTPStatus.NOT_FOUND)
                return
            synthesis_status, synthesis = get_synthesis_state(expediente)
            if synthesis_status != "current" or synthesis is None:
                self.write_error_json(
                    "Genera primero una sintesis vigente del expediente antes de evaluar defendibilidad.",
                    status=HTTPStatus.PRECONDITION_FAILED,
                )
                return
            current_text = str(version.get("extracted_text") or "").strip()
            if not current_text:
                self.write_error_json(
                    "La version seleccionada no tiene texto extraido para evaluar defendibilidad.",
                    status=HTTPStatus.UNPROCESSABLE_ENTITY,
                )
                return
            messages = build_defendability_messages(
                expediente,
                document=document,
                version=version,
                synthesis=synthesis,
            )
            ollama_response = run_ollama_chat(messages)
            raw_answer = str(ollama_response.get("message", {}).get("content") or "").strip()
            parsed = extract_json_object(raw_answer)
            gate = normalize_defendability_gate(expediente, parsed)
        except (RuntimeError, ValueError) as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_GATEWAY)
            return

        self.write_json(
            {
                "expediente_id": expediente_id,
                "document_id": document["id"],
                "document_version_id": document_version_id,
                "document_title": document.get("title"),
                "gate": gate,
                "model": OLLAMA_MODEL,
                "generated_at": utc_now_iso(),
            },
            status=HTTPStatus.CREATED,
        )

    def handle_workspace_preflight_checklist(self, expediente_id: str) -> None:
        try:
            payload = self.read_json_body()
        except ValueError as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_REQUEST)
            return

        objective = str(payload.get("objective") or "").strip()

        try:
            expediente = backend_request("GET", f"/expedientes/{expediente_id}")
            messages = build_preflight_checklist_messages(expediente, objective)
            ollama_response = run_ollama_chat(messages)
            raw_answer = str(ollama_response.get("message", {}).get("content") or "").strip()
            parsed = extract_json_object(raw_answer)
            checklist = normalize_preflight_checklist(parsed)
            current_extra = expediente.get("extra") if isinstance(expediente.get("extra"), dict) else {}
            updated_extra = {
                **current_extra,
                "pre_merits_checklist": checklist,
            }
            backend_request(
                "PATCH",
                f"/expedientes/{expediente_id}",
                payload={"extra": updated_extra},
            )
        except (RuntimeError, ValueError) as exc:
            self.write_error_json(str(exc), status=HTTPStatus.BAD_GATEWAY)
            return

        self.write_json(
            {
                "expediente_id": expediente_id,
                "model": OLLAMA_MODEL,
                "checklist": checklist,
                "generated_at": utc_now_iso(),
            },
            status=HTTPStatus.CREATED,
        )

    def handle_workspace_release(self, expediente_id: str) -> None:
        from backend.app.release_client import call_release_tool
        from backend.app.schemas.expedientes import ReleaseEvaluationCreate, ReleaseReceiptCreate

        authorization = self.headers.get("Authorization", "")
        if not authorization.lower().startswith("bearer ") or not authorization[7:].strip():
            self.write_error_json("La liberacion requiere una sesion autenticada del revisor.", status=HTTPStatus.UNAUTHORIZED)
            return
        if not MCP_URL:
            self.write_error_json("La liberacion autenticada no esta configurada.", status=HTTPStatus.SERVICE_UNAVAILABLE)
            return
        try:
            body = self.read_json_body()
            action = body.pop("action", None)
            if action == "evaluate":
                payload = ReleaseEvaluationCreate.model_validate(body)
                tool = "evaluate_document_release"
            elif action == "release":
                payload = ReleaseReceiptCreate.model_validate(body)
                tool = "release_document"
            else:
                raise ValueError("Usa evaluacion del servidor y su execution_id; verdict manual no esta permitido.")
        except ValueError:
            self.write_error_json("Bundle o solicitud de liberacion invalidos; verdict manual no esta permitido.", status=HTTPStatus.UNPROCESSABLE_ENTITY)
            return
        try:
            result = asyncio.run(call_release_tool(MCP_URL, authorization[7:].strip(), tool, expediente_id=expediente_id, payload=payload.model_dump(mode="json")))
        except Exception:
            self.write_error_json("El servidor rechazo la operacion autenticada de liberacion.", status=HTTPStatus.CONFLICT)
            return
        self.write_json(result, status=HTTPStatus.CREATED)

    def serve_static(self, request_path: str, head_only: bool = False) -> None:
        path = request_path or "/"
        if path in {"/ops", "/ops/"}:
            self.serve_file(OPERATOR_ROOT, "index.html", head_only=head_only)
            return
        if path.startswith("/ops/"):
            relative = path.removeprefix("/ops/")
            self.serve_file(OPERATOR_ROOT, relative, head_only=head_only)
            return
        if path == "/":
            self.serve_file(WORKSPACE_ROOT, "index.html", head_only=head_only)
            return
        self.serve_file(WORKSPACE_ROOT, path.lstrip("/"), head_only=head_only)

    def serve_file(self, root: Path, relative_path: str, *, head_only: bool = False) -> None:
        normalized = posixpath.normpath("/" + relative_path).lstrip("/")
        candidate = (root / normalized).resolve()
        if root not in candidate.parents and candidate != root:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        if not candidate.exists() or not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type, _encoding = mimetypes.guess_type(str(candidate))
        body = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", f"{content_type or 'application/octet-stream'}")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if not head_only:
            self.wfile.write(body)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Lexera web workspace and operator console.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), OperatorConsoleHandler)
    print(
        json.dumps(
            {
                "ok": True,
                "url": f"http://{args.host}:{args.port}",
                "repo_root": str(REPO_ROOT),
                "workspace_root": str(WORKSPACE_ROOT),
                "operator_root": str(OPERATOR_ROOT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
