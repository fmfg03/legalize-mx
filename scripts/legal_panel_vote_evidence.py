#!/usr/bin/env python3
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import secrets
from typing import Any, Dict, Iterable, List, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_hex(value: Any) -> str:
    payload = value if isinstance(value, str) else stable_json(value)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def compute_merkle_root(leaf_hashes: Iterable[str]) -> str:
    leaves = list(leaf_hashes)
    if not leaves:
        return sha256_hex("empty")

    current = leaves
    while len(current) > 1:
        if len(current) % 2 == 1:
            current.append(current[-1])
        current = [
            sha256_hex({"left": current[index], "right": current[index + 1]})
            for index in range(0, len(current), 2)
        ]
    return current[0]


@dataclass
class VoteCommitment:
    persona: str
    round_id: str
    sealed: bool
    commitment_hash: str
    reveal_nonce: str
    reveal_hash: str

    def public_view(self) -> Dict[str, Any]:
        return {
            "persona": self.persona,
            "round_id": self.round_id,
            "sealed": self.sealed,
            "commitment_hash": self.commitment_hash,
            "reveal_hash": self.reveal_hash,
        }


@dataclass
class LegalPanelEvidenceEvent:
    event_type: str
    round_id: str
    payload: Dict[str, Any]
    parent_event_id: Optional[str] = None
    ts: str = field(default_factory=utc_now_iso)
    event_id: str = ""
    payload_hash: str = ""

    def finalize(self) -> "LegalPanelEvidenceEvent":
        self.payload_hash = sha256_hex(self.payload)
        self.event_id = sha256_hex(
            {
                "event_type": self.event_type,
                "round_id": self.round_id,
                "payload_hash": self.payload_hash,
                "parent_event_id": self.parent_event_id,
                "ts": self.ts,
            }
        )
        return self

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "round_id": self.round_id,
            "ts": self.ts,
            "event_id": self.event_id,
            "parent_event_id": self.parent_event_id,
            "payload_hash": self.payload_hash,
            "payload": self.payload,
        }


def build_vote_commitments(votes: List[Dict[str, Any]]) -> List[VoteCommitment]:
    commitments: List[VoteCommitment] = []
    for vote in votes:
        reveal_payload = {
            "persona": vote["persona"],
            "round_id": vote["round_id"],
            "decision": vote["decision"],
            "confidence": vote["confidence"],
            "justification": vote["justification"],
            "structured_change_justification": vote.get("structured_change_justification"),
        }
        reveal_nonce = secrets.token_hex(16)
        reveal_hash = sha256_hex(reveal_payload)
        commitment_hash = sha256_hex({"reveal_nonce": reveal_nonce, "reveal_hash": reveal_hash})
        commitments.append(
            VoteCommitment(
                persona=vote["persona"],
                round_id=vote["round_id"],
                sealed=bool(vote.get("sealed")),
                commitment_hash=commitment_hash,
                reveal_nonce=reveal_nonce,
                reveal_hash=reveal_hash,
            )
        )
    return commitments


def build_legal_panel_vote_evidence(
    *,
    query: str,
    jurisdiction: str,
    initial_votes: List[Dict[str, Any]],
    final_votes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    commitments = build_vote_commitments(initial_votes)
    chain_id = sha256_hex(
        {
            "query": query,
            "jurisdiction": jurisdiction,
            "kind": "legal_panel_vote_protocol_v1",
        }
    )

    sealed_event = LegalPanelEvidenceEvent(
        event_type="legal_panel_vote_round_sealed_v1",
        round_id="round_1_initial_sealed",
        payload={
            "query_hash": sha256_hex(query),
            "jurisdiction": jurisdiction,
            "sealed_commitments": [commitment.public_view() for commitment in commitments],
        },
    ).finalize()

    deliberation_event = LegalPanelEvidenceEvent(
        event_type="legal_panel_deliberation_completed_v1",
        round_id="deliberation",
        parent_event_id=sealed_event.event_id,
        payload={
            "query_hash": sha256_hex(query),
            "jurisdiction": jurisdiction,
            "initial_commitment_count": len(commitments),
        },
    ).finalize()

    reveal_event = LegalPanelEvidenceEvent(
        event_type="legal_panel_vote_round_revealed_v1",
        round_id="round_2_post_deliberation",
        parent_event_id=deliberation_event.event_id,
        payload={
            "query_hash": sha256_hex(query),
            "jurisdiction": jurisdiction,
            "initial_vote_round": initial_votes,
            "final_vote_round": final_votes,
            "sealed_commitments": [commitment.public_view() for commitment in commitments],
            "reveal_material": [
                {
                    "persona": commitment.persona,
                    "round_id": commitment.round_id,
                    "reveal_nonce": commitment.reveal_nonce,
                    "reveal_hash": commitment.reveal_hash,
                    "commitment_hash": commitment.commitment_hash,
                }
                for commitment in commitments
            ],
        },
    ).finalize()

    events = [sealed_event, deliberation_event, reveal_event]
    merkle_root = compute_merkle_root(event.event_id for event in events)
    return {
        "event_type": "legal_panel_vote_protocol_evidence_v1",
        "evidence_chain_id": chain_id,
        "merkle_root": merkle_root,
        "events": [event.to_dict() for event in events],
        "initial_vote_commitments": [commitment.public_view() for commitment in commitments],
    }
