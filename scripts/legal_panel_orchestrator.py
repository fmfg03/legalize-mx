#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Dict, List, Tuple

from legal_panel_vote_evidence import build_legal_panel_vote_evidence
from route_model_execution import decide_route, load_json as load_policy_json


EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_ERROR = 2

INITIAL_ROUND_ID = "round_1_initial_sealed"
FINAL_ROUND_ID = "round_2_post_deliberation"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def require_fields(payload: Dict[str, Any], fields: List[str], section: str) -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    for field in fields:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            failures.append(
                {
                    "code": "field.missing",
                    "message": f"Falta `{field}` en {section}.",
                    "details": {"section": section, "field": field},
                }
            )
    return failures


def normalize_vote(vote: Dict[str, Any], *, round_id: str, sealed: bool) -> Dict[str, Any]:
    normalized = dict(vote)
    normalized["round_id"] = round_id
    normalized["sealed"] = sealed
    normalized["decision"] = str(normalized.get("decision", "")).strip().lower()
    normalized["confidence"] = float(normalized.get("confidence", 0.0))
    normalized["justification"] = str(normalized.get("justification", "")).strip()
    if "metadata" not in normalized or not isinstance(normalized["metadata"], dict):
        normalized["metadata"] = {}
    return normalized


def validate_votes(votes: List[Dict[str, Any]], *, round_id: str, sealed: bool) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    normalized: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    seen_personas = set()
    allowed_decisions = {"approve", "conditional", "reject", "abstain"}

    for raw_vote in votes:
        if not isinstance(raw_vote, dict):
            failures.append(
                {
                    "code": "vote.invalid",
                    "message": "Una entrada de votos no es objeto JSON.",
                    "details": {"round_id": round_id},
                }
            )
            continue
        failures.extend(require_fields(raw_vote, ["persona", "decision", "justification"], f"vote.{round_id}"))
        vote = normalize_vote(raw_vote, round_id=round_id, sealed=sealed)
        persona = vote.get("persona")
        if persona in seen_personas:
            failures.append(
                {
                    "code": "vote.duplicate_persona",
                    "message": "Una persona voto mas de una vez en la misma ronda.",
                    "details": {"round_id": round_id, "persona": persona},
                }
            )
        else:
            seen_personas.add(persona)
        if vote["decision"] not in allowed_decisions:
            failures.append(
                {
                    "code": "vote.decision.invalid",
                    "message": "La decision de voto no es valida.",
                    "details": {"round_id": round_id, "persona": persona, "decision": vote["decision"]},
                }
            )
        normalized.append(vote)

    return normalized, failures


def has_structured_change_justification(vote: Dict[str, Any]) -> bool:
    justification = vote.get("structured_change_justification")
    if not isinstance(justification, dict):
        return False
    required = {"trigger", "evidence_delta", "reasoning_delta"}
    return all(justification.get(field) for field in required)


def compare_vote_rounds(initial_votes: List[Dict[str, Any]], final_votes: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    failures: List[Dict[str, Any]] = []
    changes: List[Dict[str, Any]] = []
    initial_by_persona = {vote["persona"]: vote for vote in initial_votes}
    final_by_persona = {vote["persona"]: vote for vote in final_votes}

    if set(initial_by_persona) != set(final_by_persona):
        failures.append(
            {
                "code": "vote.persona.mismatch",
                "message": "Las dos rondas no contienen exactamente las mismas personas.",
                "details": {
                    "initial_personas": sorted(initial_by_persona),
                    "final_personas": sorted(final_by_persona),
                },
            }
        )
        return changes, failures

    for persona, initial_vote in initial_by_persona.items():
        final_vote = final_by_persona[persona]
        if initial_vote["decision"] != final_vote["decision"]:
            changes.append(
                {
                    "persona": persona,
                    "initial_decision": initial_vote["decision"],
                    "final_decision": final_vote["decision"],
                }
            )
            if not has_structured_change_justification(final_vote):
                failures.append(
                    {
                        "code": "vote_drift.unjustified",
                        "message": "El cambio de voto carece de justificacion estructurada.",
                        "details": {
                            "persona": persona,
                            "initial_decision": initial_vote["decision"],
                            "final_decision": final_vote["decision"],
                        },
                    }
                )
    return changes, failures


def safe_mean(values: List[float]) -> float:
    return float(mean(values)) if values else 0.0


def safe_variance(values: List[float]) -> float:
    return float(pstdev(values) ** 2) if len(values) > 1 else 0.0


def resolve_panel_profile(policy: Dict[str, Any], request: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    profiles = policy.get("profiles", {})
    requested_profile = request.get("matter_profile") or policy.get("default_profile")
    if not isinstance(requested_profile, str) or requested_profile not in profiles:
        raise ValueError(f"Perfil de panel no configurado: {requested_profile}")
    return requested_profile, profiles[requested_profile]


def validate_expected_personas(
    initial_votes: List[Dict[str, Any]],
    final_votes: List[Dict[str, Any]],
    expected_personas: List[str],
) -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    expected = set(expected_personas)
    initial_personas = {vote["persona"] for vote in initial_votes}
    final_personas = {vote["persona"] for vote in final_votes}
    if initial_personas != expected:
        failures.append(
            {
                "code": "panel.personas.initial_mismatch",
                "message": "La ronda inicial no coincide con las personas requeridas por el perfil.",
                "details": {
                    "expected_personas": sorted(expected),
                    "initial_personas": sorted(initial_personas),
                },
            }
        )
    if final_personas != expected:
        failures.append(
            {
                "code": "panel.personas.final_mismatch",
                "message": "La ronda final no coincide con las personas requeridas por el perfil.",
                "details": {
                    "expected_personas": sorted(expected),
                    "final_personas": sorted(final_personas),
                },
            }
        )
    return failures


def get_nested_value(payload: Dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def compute_panel_metrics(final_votes: List[Dict[str, Any]]) -> Dict[str, Any]:
    decisions = [vote["decision"] for vote in final_votes]
    confidences = [vote["confidence"] for vote in final_votes]
    counts = Counter(decisions)
    majority_decision, majority_count = counts.most_common(1)[0]
    agreement_ratio = majority_count / len(final_votes) if final_votes else 0.0
    return {
        "majority_decision": majority_decision,
        "vote_distribution": dict(counts),
        "agreement_ratio": agreement_ratio,
        "mean_confidence": safe_mean(confidences),
        "confidence_variance": safe_variance(confidences),
        "consensus_confidence": safe_mean(confidences) * agreement_ratio,
    }


def apply_profile_controls(profile_name: str, profile: Dict[str, Any], final_votes: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    failures: List[Dict[str, Any]] = []
    escalations: List[Dict[str, Any]] = []
    final_by_persona = {vote["persona"]: vote for vote in final_votes}

    for persona, blocked_decisions in (profile.get("blocking_roles") or {}).items():
        vote = final_by_persona.get(persona)
        if vote and vote["decision"] in set(blocked_decisions):
            failures.append(
                {
                    "code": "panel.role.blocked",
                    "message": "Un rol critico ejercio veto material sobre la salida.",
                    "details": {
                        "profile": profile_name,
                        "persona": persona,
                        "decision": vote["decision"],
                    },
                }
            )

    for persona, escalation_decisions in (profile.get("escalation_roles") or {}).items():
        vote = final_by_persona.get(persona)
        if vote and vote["decision"] in set(escalation_decisions):
            escalations.append(
                {
                    "code": "panel.role.escalated",
                    "message": "Un rol critico exige escalacion antes de liberar la salida.",
                    "details": {
                        "profile": profile_name,
                        "persona": persona,
                        "decision": vote["decision"],
                    },
                }
            )

    verdict = "BLOCKED" if failures else "ESCALATED" if escalations else "APPROVED"
    return verdict, failures, escalations


def validate_required_metadata(profile_name: str, profile: Dict[str, Any], final_votes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    final_by_persona = {vote["persona"]: vote for vote in final_votes}
    required_paths = profile.get("required_metadata_paths") or {}
    for persona, paths in required_paths.items():
        vote = final_by_persona.get(persona)
        if not vote:
            continue
        for path in paths:
            if get_nested_value(vote, path) in (None, ""):
                failures.append(
                    {
                        "code": "panel.metadata.required_missing",
                        "message": "Falta metadata critica exigida por el perfil.",
                        "details": {
                            "profile": profile_name,
                            "persona": persona,
                            "path": path,
                        },
                    }
                )
    return failures


def evaluate_issue_controls(profile_name: str, profile: Dict[str, Any], final_votes: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    failures: List[Dict[str, Any]] = []
    escalations: List[Dict[str, Any]] = []
    final_by_persona = {vote["persona"]: vote for vote in final_votes}
    for control in profile.get("issue_controls") or []:
        persona = control.get("persona")
        vote = final_by_persona.get(persona)
        if not vote:
            continue
        path = control.get("path")
        value = get_nested_value(vote, path) if isinstance(path, str) else None
        label = control.get("label") or path
        if value in set(control.get("block_values") or []):
            failures.append(
                {
                    "code": "panel.issue.blocked",
                    "message": "Un eje material del perfil bloquea la liberacion.",
                    "details": {
                        "profile": profile_name,
                        "persona": persona,
                        "path": path,
                        "label": label,
                        "value": value,
                    },
                }
            )
        elif value in set(control.get("escalate_values") or []):
            escalations.append(
                {
                    "code": "panel.issue.escalated",
                    "message": "Un eje material del perfil exige escalacion.",
                    "details": {
                        "profile": profile_name,
                        "persona": persona,
                        "path": path,
                        "label": label,
                        "value": value,
                    },
                }
            )
    return failures, escalations


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Orquesta un panel colegiado juridico con commitments, reveal, evidencia local y release gate."
    )
    parser.add_argument("--session", required=True, help="JSON de sesion del panel juridico.")
    parser.add_argument("--expediente-id", help="Expediente persistido para liberacion autenticada.")
    parser.add_argument("--document-version-id", help="Version persistida para liberacion autenticada.")
    parser.add_argument("--mcp-url", help="Endpoint autenticado MCP para liberacion.")
    parser.add_argument("--root", default="/root/legalize-mx", help="Raiz del repositorio.")
    parser.add_argument(
        "--policy",
        default="/root/legalize-mx/config/legal_panel_policy.json",
        help="Politica declarativa del panel juridico.",
    )
    parser.add_argument(
        "--routing-policy",
        default="/root/legalize-mx/config/hybrid_model_routing_policy.json",
        help="Politica declarativa del router hibrido.",
    )
    parser.add_argument(
        "--receipt-log",
        default="/root/legalize-mx/raw/guardrails/receipts/legal_panel_receipts.jsonl",
        help="Bitacora de recibos del panel juridico.",
    )
    parser.add_argument(
        "--artifact-dir",
        default="/root/legalize-mx/raw/legal_panel",
        help="Directorio de artefactos del panel.",
    )
    parser.add_argument(
        "--skip-release",
        action="store_true",
        help="No invoca el release gate; solo construye el panel y emite artefactos.",
    )
    args = parser.parse_args()

    root = Path(args.root)
    session_path = Path(args.session)
    policy_path = Path(args.policy)
    routing_policy_path = Path(args.routing_policy)
    receipt_log = Path(args.receipt_log)
    artifact_dir = Path(args.artifact_dir)

    try:
        session = json.loads(session_path.read_text(encoding="utf-8"))
        policy = load_policy_json(policy_path)
        routing_policy = load_policy_json(routing_policy_path)
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"panel_verdict": "ERROR", "exit_code": EXIT_ERROR, "error": str(exc)}, ensure_ascii=False, indent=2))
        return EXIT_ERROR

    request = session.get("request", {})
    draft_bundle = session.get("draft_bundle")
    initial_round_raw = session.get("initial_vote_round", [])
    final_round_raw = session.get("final_vote_round", [])

    failures: List[Dict[str, Any]] = []
    if not isinstance(request, dict):
        failures.append({"code": "request.invalid", "message": "La sesion no contiene `request` valido.", "details": {}})
        request = {}
    else:
        failures.extend(require_fields(request, ["task_id", "query", "jurisdiction"], "request"))

    if not isinstance(draft_bundle, dict):
        failures.append({"code": "draft_bundle.invalid", "message": "La sesion no contiene `draft_bundle` valido.", "details": {}})
        draft_bundle = {}

    if not isinstance(initial_round_raw, list) or not isinstance(final_round_raw, list):
        failures.append({"code": "vote_round.invalid", "message": "Las rondas de voto deben ser listas JSON.", "details": {}})
        initial_round_raw = []
        final_round_raw = []

    initial_votes, initial_failures = validate_votes(initial_round_raw, round_id=INITIAL_ROUND_ID, sealed=True)
    final_votes, final_failures = validate_votes(final_round_raw, round_id=FINAL_ROUND_ID, sealed=False)
    failures.extend(initial_failures)
    failures.extend(final_failures)

    vote_changes, drift_failures = compare_vote_rounds(initial_votes, final_votes)
    failures.extend(drift_failures)

    routing_input = {
        "task_id": request.get("task_id"),
        "task_kind": request.get("task_kind"),
        "objective": request.get("objective"),
        "complexity": request.get("complexity"),
        "consequence_level": request.get("consequence_level"),
        "requires_jurisprudence": request.get("requires_jurisprudence"),
        "writes_for_user": request.get("writes_for_user"),
        "jurisdiction": request.get("jurisdiction"),
        "query_date": request.get("query_date"),
    }
    try:
        profile_name, panel_profile = resolve_panel_profile(policy, request)
    except Exception as exc:  # noqa: BLE001
        failures.append({"code": "panel.profile.invalid", "message": str(exc), "details": {}})
        profile_name = str(request.get("matter_profile") or policy.get("default_profile"))
        panel_profile = {"panel_personas": []}

    failures.extend(validate_expected_personas(initial_votes, final_votes, panel_profile.get("panel_personas", [])))

    route_decision = decide_route(routing_input, routing_policy)
    panel_metrics = compute_panel_metrics(final_votes) if final_votes else {
        "majority_decision": None,
        "vote_distribution": {},
        "agreement_ratio": 0.0,
        "mean_confidence": 0.0,
        "confidence_variance": 0.0,
        "consensus_confidence": 0.0,
    }
    failures.extend(validate_required_metadata(profile_name, panel_profile, final_votes))
    issue_failures, issue_escalations = evaluate_issue_controls(profile_name, panel_profile, final_votes)
    failures.extend(issue_failures)
    profile_verdict, profile_failures, escalations = apply_profile_controls(profile_name, panel_profile, final_votes)
    failures.extend(profile_failures)
    escalations.extend(issue_escalations)

    blocked_decisions = set(policy.get("blocked_majority_decisions", []))
    allowed_release_decisions = set(policy.get("allowed_release_decisions", []))
    majority_decision = panel_metrics.get("majority_decision")
    if profile_verdict != "BLOCKED" and majority_decision in blocked_decisions:
        failures.append(
            {
                "code": "panel.majority.blocked",
                "message": "La decision mayoritaria del panel impide liberar el escrito.",
                "details": {"majority_decision": majority_decision},
            }
        )
    elif profile_verdict == "APPROVED" and majority_decision not in allowed_release_decisions:
        failures.append(
            {
                "code": "panel.majority.unknown",
                "message": "La decision mayoritaria no esta permitida por la politica del panel.",
                "details": {"majority_decision": majority_decision},
            }
        )

    vote_evidence = build_legal_panel_vote_evidence(
        query=str(request.get("query", "")),
        jurisdiction=str(request.get("jurisdiction", "")),
        initial_votes=initial_votes,
        final_votes=final_votes,
    )

    panel_metadata = {
        "panel_protocol": {
            "initial_round": "independent_sealed",
            "final_round": "post_deliberation",
            "change_guardrail": "structured_justification_required",
            "majority_rule": "final_round_majority",
        },
        "route_decision": route_decision,
        "panel_metrics": panel_metrics,
        "vote_changes": vote_changes,
        "initial_vote_round": initial_votes,
        "final_vote_round": final_votes,
        "initial_vote_commitments": vote_evidence["initial_vote_commitments"],
        "vote_evidence": vote_evidence,
    }

    augmented_bundle = dict(draft_bundle)
    augmented_bundle["panel_metadata"] = panel_metadata
    augmented_bundle.setdefault("request_id", request.get("task_id"))
    if request.get("jurisdiction") and not augmented_bundle.get("jurisdiction"):
        augmented_bundle["jurisdiction"] = request["jurisdiction"]
    if request.get("query_date") and not augmented_bundle.get("query_date"):
        augmented_bundle["query_date"] = request["query_date"]

    session_id = request.get("task_id") or session_path.stem
    candidate_bundle_path = artifact_dir / "candidates" / f"{session_id}.json"
    write_json(candidate_bundle_path, augmented_bundle)

    release_result: Dict[str, Any] | None = None
    release_exit_code: int | None = None
    if not failures and not escalations and not args.skip_release:
        if not args.expediente_id or not args.document_version_id or not args.mcp_url:
            release_exit_code, release_result = EXIT_BLOCKED, {"release_verdict": "BLOCKED", "reason": "authenticated_persistent_release_required"}
        else:
            # Only the repository's authenticated client may produce a release result.
            release_script_path = Path(__file__).with_name("release_legal_response.py")
            result = subprocess.run(
                [sys.executable, str(release_script_path), "--bundle", str(candidate_bundle_path),
                 "--expediente-id", args.expediente_id, "--document-version-id", args.document_version_id,
                 "--mcp-url", args.mcp_url], capture_output=True, text=True, check=False,
            )
            release_exit_code = result.returncode
            try:
                release_result = json.loads(result.stdout)
            except json.JSONDecodeError:
                release_result = {"release_verdict": "ERROR"}
        if release_exit_code != EXIT_OK or release_result.get("release_verdict") != "APPROVED" or not release_result.get("receipt", {}).get("execution_id"):
            failures.append(
                {
                    "code": "release.blocked",
                    "message": "El release gate bloqueo el bundle del panel juridico.",
                    "details": release_result or {},
                }
            )

    if failures:
        panel_verdict = "BLOCKED"
    elif escalations:
        panel_verdict = "ESCALATED"
    elif args.skip_release:
        panel_verdict = "RELEASE_PENDING"
    else:
        panel_verdict = "APPROVED"
    receipt = {
        "receipt_type": "legal_panel_receipt",
        "created_at": utc_now_iso(),
        "policy_id": policy.get("policy_id"),
        "session_path": str(session_path),
        "task_id": request.get("task_id"),
        "profile_name": profile_name,
        "profile_description": panel_profile.get("description"),
        "panel_verdict": panel_verdict,
        "route_decision": route_decision,
        "panel_metrics": panel_metrics,
        "vote_changes": vote_changes,
        "escalations": escalations,
        "candidate_bundle_path": str(candidate_bundle_path),
        "release_result": release_result,
        "failure_count": len(failures),
        "failures": failures,
    }
    append_jsonl(receipt_log, receipt)

    print(
        json.dumps(
            {
                "panel_verdict": panel_verdict,
                "exit_code": EXIT_OK if panel_verdict == "APPROVED" else EXIT_BLOCKED,
                "panel_metrics": panel_metrics,
                "vote_changes": vote_changes,
                "profile_name": profile_name,
                "required_personas": panel_profile.get("panel_personas", []),
                "escalations": escalations,
                "candidate_bundle_path": str(candidate_bundle_path),
                "receipt_log": str(receipt_log),
                "release_result": release_result,
                "failures": failures,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return EXIT_OK if panel_verdict == "APPROVED" else EXIT_BLOCKED


if __name__ == "__main__":
    raise SystemExit(main())
