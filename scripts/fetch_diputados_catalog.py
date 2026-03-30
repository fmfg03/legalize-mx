#!/usr/bin/env python3
"""
Descubre el catalogo federal base desde LeyesBiblio/index.htm de la Camara
de Diputados.

Objetivo:
1. obtener inventario de normas
2. extraer source_id desde enlaces ref/*.htm
3. capturar titulo visible y ultima reforma visible
4. clasificar cada entrada por categoria/rank con heuristicas

Salida:
- JSON con `catalog` y `errors`
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
from html.parser import HTMLParser
from pathlib import Path

import diputados_fetch_utils as fetch_utils


CATALOG_URL = "https://www.diputados.gob.mx/LeyesBiblio/index.htm"
WS_RE = re.compile(r"\s+")
REF_RE = re.compile(r"/LeyesBiblio/ref/([a-z0-9_]+)\.htm", re.IGNORECASE)
DOF_DATE_RE = re.compile(r"(DOF\s+\d{2}/\d{2}/\d{4}|Sin reforma|Notificaci[oó]n\s+\d{2}/\d{2}/\d{4}\s+Sentencia\s+SCJN)", re.IGNORECASE)


def clean_text(text: str) -> str:
    return WS_RE.sub(" ", html.unescape(text)).strip()


def infer_category_and_rank(title: str) -> tuple[str | None, str | None]:
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
    if normalized.startswith("presupuesto "):
        return "budget", "presupuesto"
    if normalized.startswith("ordenanza "):
        return "ordinance", "ordenanza"
    if normalized.startswith("estatuto "):
        return "statute", "estatuto"
    return None, None


class DiputadosCatalogParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.entries: list[dict] = []
        self.current_href: str | None = None
        self.current_text_parts: list[str] = []
        self.current_row: list[dict] = []
        self.in_td = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "tr":
            self.current_row = []
        elif tag == "td":
            self.in_td = True
            self.current_href = None
            self.current_text_parts = []
        elif tag == "a" and self.in_td:
            href = attrs_dict.get("href")
            if href:
                self.current_href = href

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self.in_td:
            text = clean_text(" ".join(self.current_text_parts))
            self.current_row.append({"href": self.current_href, "text": text})
            self.in_td = False
            self.current_href = None
            self.current_text_parts = []
        elif tag == "tr":
            entry = self._row_to_entry(self.current_row)
            if entry:
                self.entries.append(entry)
            self.current_row = []

    def handle_data(self, data: str) -> None:
        if self.in_td and data.strip():
            self.current_text_parts.append(data)

    def _row_to_entry(self, row: list[dict]) -> dict | None:
        if not row:
            return None

        source_cell: dict | None = None
        last_reform_cell: dict | None = None

        for index, cell in enumerate(row):
            href = cell.get("href") or ""
            if REF_RE.search(href):
                source_cell = cell
                if index + 1 < len(row):
                    last_reform_cell = row[index + 1]
                break

        if not source_cell:
            return None

        href = source_cell["href"]
        match = REF_RE.search(href)
        if not match:
            return None

        source_id = match.group(1).lower()
        raw_title = clean_text(source_cell["text"])
        raw_title = re.sub(r"\bDOF\s+\d{2}/\d{2}/\d{4}\b.*$", "", raw_title, flags=re.IGNORECASE).strip()
        raw_title = re.sub(r"\bNueva reforma\b", "", raw_title, flags=re.IGNORECASE).strip()
        raw_title = re.sub(r"\s+\(\s*Abrogado.*?\)\s*", " ", raw_title, flags=re.IGNORECASE).strip()
        raw_title = clean_text(raw_title)

        last_reform = None
        if last_reform_cell:
            m = DOF_DATE_RE.search(last_reform_cell["text"])
            if m:
                last_reform = clean_text(m.group(1))

        category, rank = infer_category_and_rank(raw_title)
        return {
            "source_id": source_id,
            "source_url": f"https://www.diputados.gob.mx/LeyesBiblio/ref/{source_id}.htm",
            "title": raw_title,
            "short_title": source_id.upper() if source_id.isalpha() and len(source_id) <= 8 else None,
            "category": category,
            "rank": rank,
            "last_reform": last_reform,
        }


def fetch_html(url: str, timeout: int, retries: int, retry_delay: float) -> str:
    payload, _meta = fetch_utils.fetch_url_with_cache(
        url,
        kind="text",
        timeout=timeout,
        retries=retries,
        retry_delay=retry_delay,
        queue_context={"job_type": "catalog"},
        allow_stale_cache=True,
    )
    return payload.decode("utf-8", errors="replace")


def dedupe_entries(entries: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[str] = set()
    for entry in entries:
        source_id = entry["source_id"]
        if source_id not in seen:
            deduped.append(entry)
            seen.add(source_id)
    return deduped


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Descubre el catalogo base de LeyesBiblio/index.htm."
    )
    parser.add_argument("--output", help="Ruta JSON de salida")
    parser.add_argument("--timeout", type=int, default=20, help="Timeout HTTP en segundos")
    parser.add_argument("--retries", type=int, default=2, help="Numero de reintentos HTTP")
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=1.5,
        help="Segundos de espera entre reintentos",
    )
    args = parser.parse_args()

    errors: list[dict] = []
    entries: list[dict] = []

    try:
        raw_html = fetch_html(CATALOG_URL, args.timeout, args.retries, args.retry_delay)
        html_parser = DiputadosCatalogParser()
        html_parser.feed(raw_html)
        entries = dedupe_entries(html_parser.entries)
    except urllib.error.HTTPError as exc:
        errors.append({"url": CATALOG_URL, "error": f"HTTP {exc.code}"})
    except urllib.error.URLError as exc:
        errors.append({"url": CATALOG_URL, "error": str(exc.reason)})
    except TimeoutError:
        errors.append({"url": CATALOG_URL, "error": "timeout"})

    payload = {"catalog_url": CATALOG_URL, "catalog": entries, "errors": errors}
    output = json.dumps(payload, ensure_ascii=True, indent=2) + "\n"

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
