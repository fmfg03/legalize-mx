#!/usr/bin/env python3
"""Release only through authenticated MCP and persistent server gate evidence."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.app.release_client import evaluate_and_release


def main() -> int:
    parser = argparse.ArgumentParser(description="Liberacion autenticada con gates y recibo persistente del servidor.")
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--expediente-id", required=True)
    parser.add_argument("--document-version-id", required=True)
    parser.add_argument("--mcp-url", default=os.getenv("LEGALIZE_MX_OAUTH_RESOURCE_URL", ""))
    args = parser.parse_args()
    # Existing caller session only; no token argument, prompt, credential store or fallback API key.
    token = os.getenv("LEGALIZE_MX_SESSION_BEARER", "").strip()
    try:
        bundle = json.loads(Path(args.bundle).read_text(encoding="utf-8"))
        if not isinstance(bundle, dict):
            raise ValueError("Bundle must be a JSON object")
        result = asyncio.run(evaluate_and_release(args.mcp_url, token, expediente_id=args.expediente_id, document_version_id=args.document_version_id, bundle=bundle))
    except Exception:
        print(json.dumps({"release_verdict": "ERROR", "error": "Authenticated server release failed"}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["release_verdict"] == "APPROVED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
