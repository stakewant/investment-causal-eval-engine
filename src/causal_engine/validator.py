from __future__ import annotations

from collections.abc import Iterable

from .contracts import DecisionInput, Evidence, RelationEvidence
from .errors import ContractError


def validate_decision(decision: DecisionInput, graph: dict) -> None:
    problems: list[str] = []
    if not decision.session_id:
        problems.append("session_id is required")
    if decision.scenario_id != graph.get("scenario_id"):
        problems.append("scenario_id does not match evaluator graph")
    if decision.scenario_version != graph.get("scenario_version"):
        problems.append("scenario_version does not match evaluator graph")
    if decision.turn_no != graph.get("turn_no"):
        problems.append("turn_no does not match evaluator graph")
    if not decision.answers:
        problems.append("at least one answer is required")
    answer_ids = [answer.question_id for answer in decision.answers]
    if any(not item for item in answer_ids) or len(answer_ids) != len(set(answer_ids)):
        problems.append("answer question_id values must be non-empty and unique")
    if problems:
        raise ContractError("invalid decision input: " + "; ".join(problems))


class EvidenceValidator:
    VERSION = "evidence-validator-v0.2.0"

    def __init__(self, factor_catalog: dict, graph: dict) -> None:
        self.factors = {item["factor_id"]: item for item in factor_catalog.get("factors", [])}
        self.nodes = graph.get("nodes", [])

    def validate(
        self,
        evidence: Evidence,
        *,
        answer_text: str,
        source_is_deterministic: bool,
    ) -> Evidence:
        diagnostics = list(evidence.diagnostic_codes)
        status = evidence.validation_status
        if evidence.factor_id not in self.factors:
            diagnostics.append("UNKNOWN_FACTOR")
            status = "REJECTED"
        if evidence.character_start < 0 or evidence.character_end > len(answer_text):
            diagnostics.append("SPAN_OUT_OF_RANGE")
            status = "REJECTED"
        elif answer_text[evidence.character_start : evidence.character_end] != evidence.evidence_span:
            diagnostics.append("SPAN_NOT_GROUNDED")
            status = "REJECTED"
        valid_scopes = {
            node.get("scope")
            for node in self.nodes
            if node.get("factor_id") == evidence.factor_id
        }
        if valid_scopes and evidence.scope not in valid_scopes:
            diagnostics.append("SCOPE_NOT_IN_TURN_GRAPH")
            status = "FEEDBACK_ONLY" if status != "REJECTED" else status
        if not 0 <= evidence.model_confidence <= 1:
            diagnostics.append("CONFIDENCE_OUT_OF_RANGE")
            status = "REJECTED"
        if not source_is_deterministic and evidence.model_confidence < 0.80:
            diagnostics.append("MODEL_CONFIDENCE_BELOW_SCORE_GATE")
            status = "FEEDBACK_ONLY" if status != "REJECTED" else status
        return Evidence(**{**evidence.__dict__, "validation_status": status, "diagnostic_codes": tuple(diagnostics)})


class RelationValidator:
    VERSION = "relation-validator-v0.2.0"

    def validate(
        self,
        relation: RelationEvidence,
        evidence_by_id: dict[str, Evidence],
    ) -> RelationEvidence:
        diagnostics = list(relation.diagnostic_codes)
        status = relation.validation_status
        source = evidence_by_id.get(relation.source_evidence_id)
        target = evidence_by_id.get(relation.target_evidence_id)
        if source is None or target is None:
            diagnostics.append("RELATION_ENDPOINT_MISSING")
            status = "REJECTED"
        elif source.validation_status != "SCORE_ELIGIBLE" or target.validation_status != "SCORE_ELIGIBLE":
            diagnostics.append("RELATION_ENDPOINT_NOT_SCORE_ELIGIBLE")
            status = "FEEDBACK_ONLY" if status != "REJECTED" else status
        elif source.answer_id != target.answer_id:
            diagnostics.append("CROSS_ANSWER_RELATION_NOT_ALLOWED")
            status = "REJECTED"
        if relation.explicitness != "EXPLICIT" and status == "SCORE_ELIGIBLE":
            diagnostics.append("IMPLICIT_RELATION_FEEDBACK_ONLY")
            status = "FEEDBACK_ONLY"
        if not relation.matched_edge_ids and status == "SCORE_ELIGIBLE":
            diagnostics.append("NO_CANONICAL_EDGE_MATCH")
            status = "REVIEW_REQUIRED"
        return RelationEvidence(
            **{**relation.__dict__, "validation_status": status, "diagnostic_codes": tuple(diagnostics)}
        )


def score_eligible(items: Iterable[Evidence | RelationEvidence]) -> tuple[Evidence | RelationEvidence, ...]:
    return tuple(item for item in items if item.validation_status == "SCORE_ELIGIBLE")
