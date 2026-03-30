#!/usr/bin/env python3
"""
Orquesta el bootstrap del inventario federal:

1. descarga el catalogo base desde LeyesBiblio/index.htm
2. opcionalmente enriquece entradas con fetch por ficha ref/*.htm
3. genera un JSON de inventario reutilizable

Este script no intenta descargar el texto completo. Solo deja listo el
inventario para la siguiente fase del pipeline.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import fetch_diputados_catalog as catalog
import fetch_diputados_metadata as metadata


def fetch_catalog(timeout: int, retries: int, retry_delay: float) -> tuple[list[dict], list[dict]]:
    errors: list[dict] = []
    entries: list[dict] = []
    try:
        raw_html = catalog.fetch_html(catalog.CATALOG_URL, timeout, retries, retry_delay)
        html_parser = catalog.DiputadosCatalogParser()
        html_parser.feed(raw_html)
        entries = catalog.dedupe_entries(html_parser.entries)
    except Exception as exc:  # noqa: BLE001
        errors.append({"url": catalog.CATALOG_URL, "error": str(exc)})
    return entries, errors


def merge_catalog_and_metadata(catalog_entries: list[dict], metadata_entries: list[dict]) -> list[dict]:
    metadata_by_id = {entry["source_id"]: entry for entry in metadata_entries}
    merged: list[dict] = []
    for entry in catalog_entries:
        meta = metadata_by_id.get(entry["source_id"], {})
        merged.append(
            {
                "source_id": entry["source_id"],
                "source_url": entry["source_url"],
                "title": meta.get("title") or entry.get("title"),
                "short_title": meta.get("short_title") or entry.get("short_title"),
                "category": meta.get("category") or entry.get("category"),
                "rank": meta.get("rank") or entry.get("rank"),
                "catalog_last_reform": entry.get("last_reform"),
                "metadata_last_reform_date": meta.get("last_reform_date"),
                "publication_dates": meta.get("publication_dates", []),
                "notes": meta.get("notes", []),
            }
        )
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap del inventario federal desde la Camara de Diputados."
    )
    parser.add_argument("--output", help="Ruta JSON de salida del inventario enriquecido")
    parser.add_argument("--catalog-output", help="Ruta JSON opcional para persistir el catalogo crudo")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limita el numero de entradas a enriquecer con metadata",
    )
    parser.add_argument(
        "--skip-metadata",
        action="store_true",
        help="Solo descarga el catalogo y no enriquece con fichas ref/*.htm",
    )
    parser.add_argument("--timeout", type=int, default=20, help="Timeout HTTP por solicitud")
    parser.add_argument("--retries", type=int, default=2, help="Numero de reintentos por solicitud")
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=1.5,
        help="Segundos de espera entre reintentos",
    )
    args = parser.parse_args()

    catalog_entries, errors = fetch_catalog(args.timeout, args.retries, args.retry_delay)

    if args.catalog_output:
        Path(args.catalog_output).write_text(
            json.dumps(
                {"catalog_url": catalog.CATALOG_URL, "catalog": catalog_entries, "errors": errors},
                ensure_ascii=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    metadata_entries: list[dict] = []
    if catalog_entries and not args.skip_metadata:
        selected = catalog_entries[: args.limit] if args.limit else catalog_entries
        source_ids = [entry["source_id"] for entry in selected]
        metadata_entries, metadata_errors = metadata.fetch_many(
            source_ids, args.timeout, args.retries, args.retry_delay
        )
        errors.extend(metadata_errors)

    inventory = merge_catalog_and_metadata(catalog_entries, metadata_entries)
    payload = {
        "catalog_url": catalog.CATALOG_URL,
        "inventory": inventory,
        "inventory_count": len(inventory),
        "errors": errors,
    }
    output = json.dumps(payload, ensure_ascii=True, indent=2) + "\n"

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)

    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
