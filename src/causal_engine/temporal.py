from __future__ import annotations

from datetime import datetime
from typing import Any

from .canonical import sha256_json
from .contracts import DecisionInput
from .errors import ContractError

TEMPORAL_RUNTIME_VERSION = "temporal-runtime-v0.2.0"


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ContractError("temporal timestamps require timezone offsets")
    return parsed


class TemporalPolicy:
    def __init__(self, source_claims: dict[str, Any], graph: dict[str, Any]) -> None:
        self.source_claims = source_claims
        self.graph = graph
        self.cutoff = _time(str(graph["information_cutoff_at"]))
        self.claims = {item["claim_id"]: item for item in source_claims.get("claims", [])}

    def validate_decision_visibility(self, decision: DecisionInput) -> None:
        violations = []
        visible = set(decision.visible_claim_ids)
        for claim_id in decision.visible_claim_ids:
            claim = self.claims.get(claim_id)
            if claim is None:
                violations.append(f"UNKNOWN_VISIBLE_CLAIM:{claim_id}")
                continue
            if _time(str(claim["available_at"])) > self.cutoff:
                violations.append(f"FUTURE_VISIBLE_CLAIM:{claim_id}")
            if claim.get("knowledge_role") != "AS_OF_EVIDENCE":
                violations.append(f"NON_AS_OF_VISIBLE_CLAIM:{claim_id}")
            if claim.get("visibility_status") != "VISIBLE_TO_USER":
                violations.append(f"VISIBILITY_STATUS_CONFLICT:{claim_id}")
        mandatory_references: set[str] = set()
        for node in self.graph.get("nodes", []):
            if node.get("importance") == "REQUIRED":
                mandatory_references.update(node.get("source_claim_refs", []))
        for edge in self.graph.get("edges", []):
            if edge.get("importance") == "REQUIRED":
                mandatory_references.update(edge.get("source_claim_refs", []))
        for claim_id in mandatory_references:
            claim = self.claims.get(claim_id, {})
            if claim.get("scoring_eligibility") != "MANDATORY_ELIGIBLE":
                continue
            prior_approved = claim.get("prior_knowledge", {}).get("status") == "APPROVED"
            if claim_id not in visible and not prior_approved:
                violations.append(f"MANDATORY_CLAIM_NOT_SHOWN:{claim_id}")
        if violations:
            raise ContractError("invalid visible claim snapshot: " + "; ".join(violations))

    def source_snapshot(self, decision: DecisionInput) -> dict[str, Any]:
        visible = set(decision.visible_claim_ids)
        mandatory: list[str] = []
        optional: list[str] = []
        authoring: list[str] = []
        final_review: list[str] = []
        for claim_id, claim in self.claims.items():
            role = claim.get("knowledge_role")
            eligibility = claim.get("scoring_eligibility")
            if role == "AS_OF_EVIDENCE" and claim_id in visible and eligibility == "MANDATORY_ELIGIBLE":
                mandatory.append(claim_id)
            elif role == "AS_OF_EVIDENCE" and eligibility in {"OPTIONAL_ELIGIBLE", "FEEDBACK_ONLY"}:
                optional.append(claim_id)
            if "GRAPH_AUTHORING" in claim.get("allowed_uses", []):
                authoring.append(claim_id)
            if role in {"RETROSPECTIVE_ANALYSIS", "OUTCOME_EVIDENCE"} or "FINAL_REVIEW" in claim.get("allowed_uses", []):
                final_review.append(claim_id)
        payload = {
            "source_policy_version": self.source_claims.get("source_policy_version"),
            "temporal_runtime_version": TEMPORAL_RUNTIME_VERSION,
            "information_cutoff_at": self.graph.get("information_cutoff_at"),
            "visible_claim_ids": sorted(visible),
            "mandatory_claim_ids": sorted(mandatory),
            "optional_claim_ids": sorted(optional),
            "authoring_only_claim_ids": sorted(set(authoring) - visible),
            "final_review_claim_ids": sorted(final_review),
        }
        return {**payload, "source_snapshot_hash": sha256_json(payload)}

    def parser_context(self, decision: DecisionInput, factor_catalog: dict[str, Any]) -> dict[str, Any]:
        """Return the maximum context allowed for a learned/LLM candidate parser.

        It intentionally excludes graph paths, scores, future claims and outcomes.
        """
        visible = set(decision.visible_claim_ids)
        claims = [
            {
                "claim_id": claim_id,
                "text": claim["text"],
                "evidence_span": claim["evidence_span"],
            }
            for claim_id, claim in self.claims.items()
            if claim_id in visible
            and claim.get("knowledge_role") == "AS_OF_EVIDENCE"
            and _time(str(claim["available_at"])) <= self.cutoff
            and "USER_INPUT" in claim.get("allowed_uses", [])
        ]
        return {
            "information_cutoff_at": self.graph.get("information_cutoff_at"),
            "answers": [
                {"question_id": answer.question_id, "text": answer.text, "target_entity_ids": list(answer.target_entity_ids)}
                for answer in decision.answers
            ],
            "factor_vocabulary": [
                {
                    "factor_id": factor["factor_id"],
                    "label": factor["label"],
                    "aliases": factor.get("aliases", []),
                    "entity_types": factor.get("entity_types", []),
                }
                for factor in factor_catalog.get("factors", [])
            ],
            "entities": factor_catalog.get("entities", []),
            "visible_as_of_claims": claims,
        }
