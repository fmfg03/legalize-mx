#!/usr/bin/env python3
"""
Descarga fichas de la Camara de Diputados desde /LeyesBiblio/ref/{id}.htm
y extrae metadatos basicos para bootstrap de legislacion federal.

Salida:
- JSON a stdout o a un archivo
- un registro por norma

Esta version prioriza robustez minima:
1. titulo
2. source_id
3. source_url
4. last_reform_date
5. publication_dates visibles
6. category/rank por heuristica
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

if __package__:
    from . import diputados_fetch_utils as fetch_utils
else:
    import diputados_fetch_utils as fetch_utils


BASE_URL = "https://www.diputados.gob.mx/LeyesBiblio/ref/{source_id}.htm"


DATE_RE = re.compile(r"\b(\d{2}-\d{2}-\d{4})\b")
LAST_REFORM_RE = re.compile(
    r"Ultima\s+reforma\s+publicada\s+en\s+el\s+Diario\s+Oficial\s+de\s+la\s+Federacion\s+el\s+(\d{2}-\d{2}-\d{4})",
    re.IGNORECASE,
)
TITLE_RE = re.compile(r"<title>\s*(.*?)\s*</title>", re.IGNORECASE | re.DOTALL)
BODY_TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


@dataclass
class DiputadosMetadata:
    source_id: str
    source_url: str
    title: str | None
    short_title: str | None
    category: str | None
    rank: str | None
    last_reform_date: str | None
    publication_dates: list[str]
    notes: list[str]


def fetch_html(url: str, timeout: int, retries: int, retry_delay: float, source_id: str) -> str:
    payload, _meta = fetch_utils.fetch_url_with_cache(
        url,
        kind="text",
        timeout=timeout,
        retries=retries,
        retry_delay=retry_delay,
        queue_context={"job_type": "metadata", "source_id": source_id},
        allow_stale_cache=True,
    )
    return payload.decode("utf-8", errors="replace")


def html_to_text(raw_html: str) -> str:
    text = TITLE_RE.sub(lambda m: f" {m.group(1)} ", raw_html)
    text = BODY_TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = WS_RE.sub(" ", text)
    return text.strip()


def extract_title(raw_html: str, plain_text: str) -> str | None:
    match = TITLE_RE.search(raw_html)
    if match:
        title = WS_RE.sub(" ", html.unescape(match.group(1))).strip(" |-")
        if title:
            return title
    # Fallback: usar el texto inicial si el <title> no sirve.
    return plain_text[:160] or None


def clean_title(title: str | None) -> str | None:
    if not title:
        return None
    title = title.replace("Cámara de Diputados del H. Congreso de la Unión", "").strip(" |-")
    return WS_RE.sub(" ", title).strip() or None


def infer_category_and_rank(title: str | None) -> tuple[str | None, str | None]:
    if not title:
        return None, None
    normalized = title.lower()
    if "constitucion politica de los estados unidos mexicanos" in normalized:
        return "constitution", "constitucion"
    if normalized.startswith("codigo "):
        return "code", "codigo"
    if normalized.startswith("ley organica "):
        return "law", "ley_organica"
    if normalized.startswith("ley reglamentaria "):
        return "law", "ley_reglamentaria"
    if normalized.startswith("ley general "):
        return "law", "ley_general"
    if normalized.startswith("ley "):
        return "law", "ley"
    if normalized.startswith("reglamento "):
        return "regulation", "reglamento"
    return None, None


def infer_short_title(title: str | None, source_id: str) -> str | None:
    if source_id.isalpha() and len(source_id) <= 8:
        return source_id.upper()
    if not title:
        return None
    if "constitucion politica de los estados unidos mexicanos" in title.lower():
        return "CPEUM"
    return None


def extract_last_reform_date(plain_text: str) -> str | None:
    match = LAST_REFORM_RE.search(plain_text)
    if match:
        return match.group(1)
    return None


def extract_publication_dates(plain_text: str) -> list[str]:
    seen: set[str] = set()
    dates: list[str] = []
    for match in DATE_RE.finditer(plain_text):
        value = match.group(1)
        if value not in seen:
            dates.append(value)
            seen.add(value)
    return dates


def parse_metadata(source_id: str, raw_html: str) -> DiputadosMetadata:
    plain_text = html_to_text(raw_html)
    title = clean_title(extract_title(raw_html, plain_text))
    category, rank = infer_category_and_rank(title)
    return DiputadosMetadata(
        source_id=source_id,
        source_url=BASE_URL.format(source_id=source_id),
        title=title,
        short_title=infer_short_title(title, source_id),
        category=category,
        rank=rank,
        last_reform_date=extract_last_reform_date(plain_text),
        publication_dates=extract_publication_dates(plain_text),
        notes=[],
    )


def load_ids(args: argparse.Namespace) -> list[str]:
    ids: list[str] = []
    if args.ids:
        ids.extend(args.ids)
    if args.ids_file:
        file_ids = [
            line.strip()
            for line in Path(args.ids_file).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        ids.extend(file_ids)
    deduped: list[str] = []
    seen: set[str] = set()
    for source_id in ids:
        if source_id not in seen:
            deduped.append(source_id)
            seen.add(source_id)
    return deduped


def fetch_many(
    source_ids: Iterable[str], timeout: int, retries: int, retry_delay: float
) -> tuple[list[dict], list[dict]]:
    records: list[dict] = []
    errors: list[dict] = []
    for source_id in source_ids:
        url = BASE_URL.format(source_id=source_id)
        try:
            raw_html = fetch_html(url, timeout, retries, retry_delay, source_id)
            metadata = parse_metadata(source_id, raw_html)
            records.append(asdict(metadata))
        except urllib.error.HTTPError as exc:
            errors.append({"source_id": source_id, "source_url": url, "error": f"HTTP {exc.code}"})
        except urllib.error.URLError as exc:
            errors.append({"source_id": source_id, "source_url": url, "error": str(exc.reason)})
        except TimeoutError:
            errors.append({"source_id": source_id, "source_url": url, "error": "timeout"})
    return records, errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extrae metadatos basicos desde fichas ref/*.htm de la Camara de Diputados."
    )
    parser.add_argument("--ids", nargs="*", help="Lista de source_id, por ejemplo: cpeum ccf cpf")
    parser.add_argument("--ids-file", help="Archivo con un source_id por linea")
    parser.add_argument("--output", help="Ruta de salida JSON")
    parser.add_argument("--timeout", type=int, default=20, help="Timeout por solicitud HTTP en segundos")
    parser.add_argument("--retries", type=int, default=2, help="Numero de reintentos por solicitud")
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=1.5,
        help="Segundos de espera entre reintentos",
    )
    args = parser.parse_args()

    source_ids = load_ids(args)
    if not source_ids:
        parser.error("Debes proporcionar --ids o --ids-file")

    records, errors = fetch_many(source_ids, args.timeout, args.retries, args.retry_delay)
    payload = {"documents": records, "errors": errors}
    output = json.dumps(payload, ensure_ascii=True, indent=2) + "\n"

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
