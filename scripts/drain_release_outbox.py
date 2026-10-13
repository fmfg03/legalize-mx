"""Export committed release events locally. No connector, credential or network effect."""
from __future__ import annotations

import json

from backend.app.config import settings
from backend.app.db import SessionLocal
from backend.app.outbox import drain_outbox


if __name__ == "__main__":
    print(json.dumps(drain_outbox(SessionLocal, settings.storage_root / "releases" / "outbox")))
