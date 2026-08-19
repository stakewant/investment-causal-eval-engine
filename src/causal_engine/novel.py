from __future__ import annotations

from typing import Any

from .canonical import sha256_json
from .contracts import Evidence, RelationEvidence

NOVEL_PATH_REVIEW_VERSION = "novel-path-review-v0.2.0"


def collect_novel_path_candidates(
    evidence: tuple[Evidence, ...],
    relations: tuple[RelationEvidence, ...],
    graph: dict[str, Any],
) -> list[dict[str, Any]]:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    graph_entities = {
        entity_id for node in graph.get("nodes", []) for entity_id in node.get("entity_ids", [])
    }
    candidates = []
    for relation in relations:
        if relation.validation_status != "REVIEW_REQUIRED":
            continue
        source = evidence_by_id.get(relation.source_evidence_id)
        target = evidence_by_id.get(relation.target_evidence_id)
        if source is None or target is None:
            continue
        entity_ids = sorted(set(source.entity_ids) | set(target.entity_ids))
        unsupported_entity = bool(set(entity_ids) - graph_entities)
        if relation.sentence_distance > 1:
            status = "OVEREXTENDED_PATH"
        elif unsupported_entity:
            status = "UNSUPPORTED_PATH"
        else:
            status = "REVIEW_REQUIRED"
        payload = {
            "source_factor_id": source.factor_id,
            "target_factor_id": target.factor_id,
            "relation": relation.relation,
            "sign": relation.sign,
            "entity_ids": entity_ids,
            "evidence_ids": [source.evidence_id, target.evidence_id],
            "relation_evidence_id": relation.relation_evidence_id,
        }
        candidates.append(
            {
                "candidate_id": "NPC-" + sha256_json(payload).removeprefix("sha256:")[:16],
                "review_version": NOVEL_PATH_REVIEW_VERSION,
                "status": status,
                **payload,
                "automatic_score_effect": 0,
            }
        )
    return candidates
