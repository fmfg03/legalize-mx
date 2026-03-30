#!/usr/bin/env python3
"""
Descarga un PDF de LeyesBiblio/pdf/*.pdf y extrae texto plano con pypdf.

Uso principal:
1. recibir source_id como cpeum, ccf, cpf
2. descargar el PDF vigente
3. guardar copia en raw/
4. extraer texto plano a txt
5. emitir metadata de extraccion
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import diputados_fetch_utils as fetch_utils

try:
    from pypdf import PdfReader
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "pypdf no esta disponible. Ejecuta este script con /root/legalize-mx/.venv/bin/python "
        "o instala dependencias en la venv del proyecto."
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "raw" / "diputados"
TEXT_DIR = RAW_DIR / "text"
PDF_DIR = RAW_DIR / "pdf"
PDF_URL_TEMPLATE = "https://www.diputados.gob.mx/LeyesBiblio/pdf/{source_id_upper}.pdf"
USER_AGENT = "legalize-mx/0.1 (+https://legalize-mx.local)"
MULTIBLANK_RE = re.compile(r"\n{3,}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def fetch_bytes(url: str, timeout: int, retries: int, retry_delay: float, source_id: str | None) -> bytes:
    payload, _meta = fetch_utils.fetch_url_with_cache(
        url,
        kind="binary",
        timeout=timeout,
        retries=retries,
        retry_delay=retry_delay,
        queue_context={"job_type": "pdf", "source_id": source_id},
        allow_stale_cache=True,
    )
    return payload


def clean_extracted_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("-\n", "")
    text = MULTIBLANK_RE.sub("\n\n", text)
    return text.strip() + "\n"


def extract_pdf_text(pdf_path: Path) -> tuple[str, int]:
    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text() or ""
        pages.append(page_text.strip())
    raw_text = "\n\n".join(pages)
    return clean_extracted_text(raw_text), len(reader.pages)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Descarga y extrae texto de PDFs de LeyesBiblio."
    )
    parser.add_argument("--source-id", help="Identificador de la norma, por ejemplo cpeum, ccf, cpf")
    parser.add_argument("--pdf-url", help="URL directa del PDF. Si se omite, se construye desde --source-id")
    parser.add_argument("--pdf-file", help="Ruta local a un PDF ya descargado")
    parser.add_argument("--output-text", help="Ruta del TXT de salida")
    parser.add_argument("--output-meta", help="Ruta del JSON de metadata de salida")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout HTTP en segundos")
    parser.add_argument("--retries", type=int, default=2, help="Numero de reintentos HTTP")
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=1.5,
        help="Segundos de espera entre reintentos",
    )
    args = parser.parse_args()

    if not args.pdf_file and not args.source_id and not args.pdf_url:
        parser.error("Debes indicar --source-id, --pdf-url o --pdf-file")

    source_id = (args.source_id or "").lower() or None
    pdf_url = args.pdf_url
    if not pdf_url and source_id:
        pdf_url = PDF_URL_TEMPLATE.format(source_id_upper=source_id.upper())

    PDF_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    if args.pdf_file:
        pdf_path = Path(args.pdf_file)
        pdf_bytes = pdf_path.read_bytes()
    else:
        assert pdf_url is not None
        pdf_bytes = fetch_bytes(pdf_url, args.timeout, args.retries, args.retry_delay, source_id)
        filename = f"{source_id or 'document'}.pdf"
        pdf_path = PDF_DIR / filename
        pdf_path.write_bytes(pdf_bytes)

    text, page_count = extract_pdf_text(pdf_path)
    text_path = Path(args.output_text) if args.output_text else TEXT_DIR / f"{(source_id or pdf_path.stem)}.txt"
    text_path.write_text(text, encoding="utf-8")

    metadata = {
        "source_id": source_id,
        "pdf_url": pdf_url,
        "pdf_path": str(pdf_path),
        "text_path": str(text_path),
        "page_count": page_count,
        "pdf_sha256": sha256_bytes(pdf_bytes),
        "text_sha256": sha256_text(text),
    }

    if args.output_meta:
        Path(args.output_meta).write_text(
            json.dumps(metadata, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
    else:
        sys.stdout.write(json.dumps(metadata, ensure_ascii=True, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
