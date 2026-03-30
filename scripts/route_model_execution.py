#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List


LOCAL_TASK_KINDS = {
    "retrieval",
    "chunking",
    "classification",
    "citation_formatting",
    "summarization",
    "normalization",
    "rewrite",
    "draft_cleanup",
    "schema_validation",
}

REASONING_TASK_KINDS = {
    "strategy",
    "argument_selection",
    "issue_spotting",
    "risk_assessment",
    "legal_theory",
    "conflict_resolution",
    "recommendation",
    "conclusion",
    "demand_drafting",
}


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_handoffs(task: Dict[str, Any], policy: Dict[str, Any], route: str) -> List[Dict[str, Any]]:
    if route == "local_ollama":
        return [
            {
                "stage": "execute",
                "provider": policy["providers"]["local_provider"],
                "requires": policy["handoff_contracts"]["local_ollama"]["requires"],
            }
        ]
    if route == "anthropic_api":
        return [
            {
                "stage": "reason",
                "provider": policy["providers"]["reasoning_provider"],
                "requires": policy["handoff_contracts"]["anthropic_api"]["requires"],
            }
        ]
    return [
        {
            "stage": "reason",
            "provider": policy["providers"]["reasoning_provider"],
            "requires": policy["handoff_contracts"]["anthropic_api"]["requires"],
        },
        {
            "stage": "execute",
            "provider": policy["providers"]["local_provider"],
            "requires": policy["handoff_contracts"]["local_ollama"]["requires"],
        },
        {
            "stage": "panel",
            "provider": "legalize_mx_legal_panel",
            "requires": ["legal_panel_session", "sealed_first_round", "vote_reveal_evidence"],
        },
        {
            "stage": "release",
            "provider": "legalize_mx_guardrails",
            "requires": ["assistant_response_bundle", "grounding_gate_pass"],
        },
    ]


def decide_route(task: Dict[str, Any], policy: Dict[str, Any]) -> Dict[str, Any]:
    task_kind = task.get("task_kind")
    complexity = task.get("complexity")
    consequence_level = task.get("consequence_level")
    requires_jurisprudence = bool(task.get("requires_jurisprudence"))
    writes_for_user = bool(task.get("writes_for_user"))

    if task_kind in LOCAL_TASK_KINDS and not writes_for_user:
        route = "local_ollama"
        reason = "Tarea operativa y mecanica; no exige deliberacion juridica compleja."
    elif (
        task_kind in REASONING_TASK_KINDS
        and (complexity in {"high", "very_high"} or consequence_level in {"high", "critical"})
        and not writes_for_user
    ):
        route = "anthropic_api"
        reason = "Tarea de razonamiento complejo sin liberacion directa de escrito al usuario."
    elif writes_for_user and (requires_jurisprudence or consequence_level in {"high", "critical"}):
        route = "hybrid"
        reason = "Escrito juridico con impacto alto; requiere razonamiento fuerte, ejecucion local y gate de liberacion."
    elif task_kind in REASONING_TASK_KINDS:
        route = "anthropic_api"
        reason = "La tarea es principalmente deliberativa."
    else:
        route = "local_ollama"
        reason = "La tarea cae en la capa operativa por defecto."

    return {
        "route": route,
        "reason": reason,
        "handoffs": build_handoffs(task, policy, route),
        "must_pass_release_gate": bool(writes_for_user),
        "legal_panel_script": policy.get("legal_panel_script") if route == "hybrid" else None,
        "release_gate_script": policy.get("release_gate_script") if writes_for_user else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Decide si una tarea juridica va a Anthropic, a modelo local o a pipeline hibrido."
    )
    parser.add_argument("--task", required=True, help="JSON con la descripcion estructurada de la tarea.")
    parser.add_argument(
        "--policy",
        default="/root/legalize-mx/config/hybrid_model_routing_policy.json",
        help="Politica declarativa de ruteo.",
    )
    args = parser.parse_args()

    task = load_json(Path(args.task))
    policy = load_json(Path(args.policy))
    decision = decide_route(task, policy)

    print(
        json.dumps(
            {
                "task_id": task.get("task_id"),
                "task_kind": task.get("task_kind"),
                "decision": decision,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
