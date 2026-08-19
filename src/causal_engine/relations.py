from __future__ import annotations

from collections import defaultdict
from typing import Any

from .contracts import AnswerInput, Evidence, RelationEvidence
from .validator import RelationValidator

RELATION_EXTRACTOR_VERSION = "hybrid-relation-v0.2.0"

PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("CONDITIONAL_ON", ("경우", "라면", "다면", "전제", "조건")),
    ("MITIGATES", ("완화", "상쇄", "줄여", "제한", "방어")),
    ("DECREASES", ("감소", "악화", "하락", "압박", "둔화", "줄어", "떨어")),
    ("AMPLIFIES", ("증폭", "가속", "더욱", "강화")),
    ("EXPOSES", ("노출", "비중", "사업", "제품", "매출")),
    ("PRICES_IN", ("선반영", "가격에 반영", "주가에 반영")),
    ("INCREASES", ("증가", "확대", "개선", "상승", "늘어", "수혜", "호조")),
    ("CAUSES", ("때문", "따라", "이어", "영향", "연결", "초래", "유발", "결과", "반영")),
)


class HybridRelationExtractor:
    def __init__(self, graph: dict[str, Any]) -> None:
        self.graph = graph
        self.validator = RelationValidator()
        nodes = {node["node_id"]: node for node in graph.get("nodes", [])}
        self.edges_by_factor_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for edge in graph.get("edges", []):
            source = nodes.get(edge.get("from_node"), {})
            target = nodes.get(edge.get("to_node"), {})
            self.edges_by_factor_pair[(source.get("factor_id"), target.get("factor_id"))].append(edge)

    def extract(
        self,
        answers: tuple[AnswerInput, ...],
        evidence: tuple[Evidence, ...],
        *,
        model_candidates: tuple[dict[str, Any], ...] = (),
    ) -> tuple[RelationEvidence, ...]:
        answers_by_id = {answer.question_id: answer for answer in answers}
        evidence_by_id = {item.evidence_id: item for item in evidence}
        grouped: dict[str, list[Evidence]] = defaultdict(list)
        for item in evidence:
            if item.validation_status != "REJECTED":
                grouped[item.answer_id].append(item)
        result: list[RelationEvidence] = []
        sequence = 1
        for answer_id, items in grouped.items():
            answer = answers_by_id[answer_id]
            ordered = sorted(items, key=lambda item: (item.character_start, item.character_end))
            for source_index, source in enumerate(ordered):
                for target in ordered[source_index + 1 :]:
                    distance = target.sentence_index - source.sentence_index
                    if distance > 1:
                        break
                    edges = self.edges_by_factor_pair.get((source.factor_id, target.factor_id), [])
                    if not edges:
                        continue
                    between = answer.text[source.character_end:target.character_start]
                    suffix = answer.text[target.character_end : min(len(answer.text), target.character_end + 18)]
                    suffix = suffix.split(",", 1)[0].split(".", 1)[0].split(";", 1)[0]
                    connector = (between + " " + suffix).strip()
                    relation = self._classify(connector)
                    explicit = relation is not None
                    if relation is None:
                        relation = "CAUSES"
                    matched = tuple(
                        edge["edge_id"] for edge in edges if self._compatible(relation, edge.get("relation"))
                    )
                    sign = self._sign(relation, target)
                    item = RelationEvidence(
                        relation_evidence_id=f"REV-{sequence:04d}",
                        source_evidence_id=source.evidence_id,
                        target_evidence_id=target.evidence_id,
                        relation=relation,
                        sign=sign,
                        connector_span=connector,
                        sentence_distance=max(0, distance),
                        explicitness="EXPLICIT" if explicit else "IMPLICIT",
                        model_confidence=1.0 if explicit else 0.55,
                        matched_edge_ids=matched,
                        validation_status="SCORE_ELIGIBLE" if explicit else "FEEDBACK_ONLY",
                        relation_extractor_version=RELATION_EXTRACTOR_VERSION,
                    )
                    result.append(self.validator.validate(item, evidence_by_id))
                    sequence += 1

        for candidate in model_candidates:
            source_id = str(candidate.get("source_evidence_id", ""))
            target_id = str(candidate.get("target_evidence_id", ""))
            source = evidence_by_id.get(source_id)
            target = evidence_by_id.get(target_id)
            if source is None or target is None:
                continue
            edges = self.edges_by_factor_pair.get((source.factor_id, target.factor_id), [])
            relation_name = str(candidate.get("relation", "CAUSES"))
            matched = tuple(
                edge["edge_id"] for edge in edges if self._compatible(relation_name, edge.get("relation"))
            )
            item = RelationEvidence(
                relation_evidence_id=f"REV-{sequence:04d}",
                source_evidence_id=source_id,
                target_evidence_id=target_id,
                relation=relation_name,
                sign=str(candidate.get("sign", self._sign(relation_name, target))),
                connector_span=str(candidate.get("connector_span", "")),
                sentence_distance=abs(target.sentence_index - source.sentence_index),
                explicitness=str(candidate.get("explicitness", "IMPLICIT")),
                model_confidence=float(candidate.get("model_confidence", 0)),
                matched_edge_ids=matched,
                validation_status="SCORE_ELIGIBLE",
                relation_extractor_version=str(candidate.get("relation_extractor_version", "external-model")),
            )
            result.append(self.validator.validate(item, evidence_by_id))
            sequence += 1
        return self._deduplicate(result)

    @staticmethod
    def _classify(connector: str) -> str | None:
        for relation, cues in PATTERNS:
            if any(cue in connector for cue in cues):
                return relation
        return None

    @staticmethod
    def _compatible(candidate: str, canonical: str | None) -> bool:
        if candidate == canonical:
            return True
        causal_family = {"CAUSES", "INCREASES", "DECREASES", "AMPLIFIES", "MITIGATES", "EXPOSES"}
        return candidate in causal_family and canonical in causal_family

    @staticmethod
    def _sign(relation: str, target: Evidence) -> str:
        if relation in {"DECREASES", "MITIGATES"}:
            return "NEGATIVE"
        if relation == "CONDITIONAL_ON" or target.certainty == "CONDITIONAL":
            return "CONDITIONAL"
        return target.direction if target.direction in {"POSITIVE", "NEGATIVE", "MIXED"} else "POSITIVE"

    @staticmethod
    def _deduplicate(items: list[RelationEvidence]) -> tuple[RelationEvidence, ...]:
        best: dict[tuple[str, str, str], RelationEvidence] = {}
        rank = {"SCORE_ELIGIBLE": 3, "FEEDBACK_ONLY": 2, "REVIEW_REQUIRED": 1, "REJECTED": 0}
        for item in items:
            key = (item.source_evidence_id, item.target_evidence_id, item.relation)
            previous = best.get(key)
            if previous is None or (rank[item.validation_status], item.model_confidence) > (
                rank[previous.validation_status],
                previous.model_confidence,
            ):
                best[key] = item
        return tuple(sorted(best.values(), key=lambda item: item.relation_evidence_id))
