from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
RULES_PATH = REPO_ROOT / "config" / "procedural_deadline_rules.json"


@dataclass(slots=True)
class ProceduralRuleMatch:
    rule_id: str
    track_id: str
    track_label: str
    trigger_event_type: str
    trigger_document_type: str | None
    deadline_label: str
    due_at: datetime
    status: str
    notes: str
    source_article: str | None
    source_url: str | None
    requires_review: bool
    computation_kind: str
    warning: str | None
    extra: dict[str, Any]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _next_weekday(value: datetime) -> datetime:
    candidate = value
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def add_weekday_business_days(reference_at: datetime, business_days: int) -> datetime:
    current = _next_weekday(_ensure_utc(reference_at))
    added_days = 0
    while added_days < business_days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            added_days += 1
    return current


@lru_cache(maxsize=1)
def load_procedural_deadline_catalog() -> dict[str, Any]:
    if not RULES_PATH.exists():
        return {"catalog_version": "missing", "tracks": []}
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def procedural_deadline_tracks() -> list[dict[str, Any]]:
    catalog = load_procedural_deadline_catalog()
    tracks = catalog.get("tracks") or []
    summaries: list[dict[str, Any]] = []
    for track in tracks:
        if not isinstance(track, dict):
            continue
        rules = [rule for rule in (track.get("rules") or []) if isinstance(rule, dict)]
        summaries.append(
            {
                "id": track.get("id"),
                "label": track.get("label"),
                "status": track.get("status"),
                "scope": track.get("scope"),
                "jurisdiction_level": track.get("jurisdiction_level"),
                "matter_types": track.get("matter_types") or [],
                "notes": track.get("notes"),
                "rule_count": len(rules),
                "sources": track.get("sources") or [],
            }
        )
    return summaries


def procedural_track_summary(track_id: str | None) -> dict[str, Any] | None:
    if not track_id:
        return None
    for track in procedural_deadline_tracks():
        if track.get("id") == track_id:
            return track
    return None


def infer_track_id(expediente: Any) -> str | None:
    extra = getattr(expediente, "extra", None)
    if isinstance(extra, dict):
        track_id = extra.get("procedure_track")
        if isinstance(track_id, str) and track_id.strip():
            return track_id.strip()
    return None


def procedural_deadline_matches(*, expediente: Any, event: Any, document: Any | None) -> list[ProceduralRuleMatch]:
    track_id = infer_track_id(expediente)
    if not track_id:
        return []

    catalog = load_procedural_deadline_catalog()
    track = next(
        (
            item
            for item in (catalog.get("tracks") or [])
            if isinstance(item, dict) and item.get("id") == track_id
        ),
        None,
    )
    if track is None:
        return []

    event_type = str(getattr(event, "event_type", "") or "")
    document_type = str(getattr(document, "document_type", "") or "") if document is not None else None
    reference_at = _ensure_utc(getattr(event, "event_date"))
    matches: list[ProceduralRuleMatch] = []

    for rule in track.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        trigger = rule.get("trigger") or {}
        if trigger.get("event_type") != event_type:
            continue
        required_document_type = trigger.get("document_type")
        if required_document_type and required_document_type != document_type:
            continue

        deadline_spec = rule.get("deadline") or {}
        business_days = int(deadline_spec.get("days_business") or 0)
        if business_days <= 0:
            continue
        due_at = add_weekday_business_days(reference_at, business_days)
        source = rule.get("source") or {}
        extra = {
            "procedural_rule_id": rule.get("id"),
            "procedural_track_id": track.get("id"),
            "procedural_track_label": track.get("label"),
            "trigger_event_type": event_type,
            "trigger_document_type": document_type,
            "generated_from_event_id": str(getattr(event, "id")),
            "requires_review": bool(rule.get("requires_review", True)),
            "computation_kind": "weekday_business_days",
            "days_business": business_days,
            "source_article": source.get("article"),
            "source_url": source.get("url"),
            "warning": rule.get("warning"),
        }
        matches.append(
            ProceduralRuleMatch(
                rule_id=str(rule.get("id") or ""),
                track_id=str(track.get("id") or ""),
                track_label=str(track.get("label") or ""),
                trigger_event_type=event_type,
                trigger_document_type=document_type,
                deadline_label=str(deadline_spec.get("label") or "Plazo procesal"),
                due_at=due_at,
                status=str(deadline_spec.get("status") or "open"),
                notes=str(rule.get("notes") or "").strip(),
                source_article=source.get("article"),
                source_url=source.get("url"),
                requires_review=bool(rule.get("requires_review", True)),
                computation_kind="weekday_business_days",
                warning=rule.get("warning"),
                extra=extra,
            )
        )
    return matches
