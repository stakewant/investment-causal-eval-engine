from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from .contracts import AnswerInput, Evidence
from .text import find_literal_spans, sentence_index_at, split_sentences, window
from .validator import EvidenceValidator

EXTRACTOR_VERSION = "hybrid-evidence-v0.2.0"

POSITIVE_CUES = ("증가", "확대", "성장", "개선", "상승", "강화", "수혜", "호조", "늘")
NEGATIVE_CUES = ("감소", "축소", "둔화", "악화", "하락", "약화", "피해", "부진", "줄")
NEGATION_CUES = ("아니다", "않", "못", "없", "제한적", "불확실")
CONDITIONAL_CUES = ("경우", "라면", "다면", "전제", "조건", "수도", "가능")
LIKELY_CUES = ("전망", "예상", "기대", "가능", "것 같다", "듯")


class HybridEvidenceExtractor:
    """Grounded candidate extractor.

    Exact author aliases are deterministic candidates. External neural/LLM candidates
    may be supplied, but must keep exact character offsets and pass the same validator.
    """

    def __init__(self, factor_catalog: dict[str, Any], graph: dict[str, Any]) -> None:
        self.catalog = factor_catalog
        self.graph = graph
        self.validator = EvidenceValidator(factor_catalog, graph)
        self.nodes_by_factor: dict[str, list[dict[str, Any]]] = {}
        for node in graph.get("nodes", []):
            self.nodes_by_factor.setdefault(node["factor_id"], []).append(node)
        self.entity_aliases = self._build_entity_aliases(factor_catalog, graph)

    @staticmethod
    def _build_entity_aliases(catalog: dict[str, Any], graph: dict[str, Any]) -> dict[str, tuple[str, ...]]:
        aliases: dict[str, set[str]] = {}
        for entity in catalog.get("entities", []):
            entity_id = str(entity.get("entity_id", ""))
            aliases.setdefault(entity_id, set()).update(
                [str(entity.get("label", "")), *[str(item) for item in entity.get("aliases", [])]]
            )
        for node in graph.get("nodes", []):
            for entity_id in node.get("entity_ids", []):
                aliases.setdefault(str(entity_id), set()).add(str(entity_id))
        return {key: tuple(sorted((item for item in values if item), key=len, reverse=True)) for key, values in aliases.items()}

    def extract(
        self,
        answers: tuple[AnswerInput, ...],
        *,
        model_candidates: tuple[dict[str, Any], ...] = (),
    ) -> tuple[Evidence, ...]:
        answer_map = {answer.question_id: answer for answer in answers}
        evidence: list[Evidence] = []
        sequence = 1
        for answer in answers:
            sentences = split_sentences(answer.text)
            occupied: set[tuple[str, int, int]] = set()
            factors = sorted(
                self.catalog.get("factors", []),
                key=lambda item: max((len(str(alias)) for alias in self._aliases(item)), default=0),
                reverse=True,
            )
            for factor in factors:
                aliases = sorted(self._aliases(factor), key=len, reverse=True)
                for alias in aliases:
                    for start, end in find_literal_spans(answer.text, alias):
                        key = (factor["factor_id"], start, end)
                        if key in occupied:
                            continue
                        occupied.add(key)
                        item = self._make_evidence(
                            evidence_id=f"EV-{sequence:04d}",
                            answer=answer,
                            factor=factor,
                            start=start,
                            end=end,
                            sentences=sentences,
                            sources=("RULE",),
                            confidence=1.0,
                        )
                        evidence.append(self.validator.validate(item, answer_text=answer.text, source_is_deterministic=True))
                        sequence += 1

        for candidate in model_candidates:
            answer = answer_map.get(str(candidate.get("answer_id", "")))
            factor = next(
                (item for item in self.catalog.get("factors", []) if item.get("factor_id") == candidate.get("factor_id")),
                None,
            )
            if answer is None or factor is None:
                continue
            start = int(candidate.get("character_start", -1))
            end = int(candidate.get("character_end", -1))
            duplicate = next(
                (
                    item
                    for item in evidence
                    if item.answer_id == answer.question_id
                    and item.factor_id == factor["factor_id"]
                    and item.character_start == start
                    and item.character_end == end
                ),
                None,
            )
            if duplicate:
                merged_sources = tuple(sorted(set(duplicate.extractor_sources) | {str(candidate.get("source", "NEURAL"))}))
                index = evidence.index(duplicate)
                evidence[index] = replace(
                    duplicate,
                    extractor_sources=merged_sources,
                    model_confidence=max(duplicate.model_confidence, float(candidate.get("model_confidence", 0))),
                )
                continue
            item = self._make_evidence(
                evidence_id=f"EV-{sequence:04d}",
                answer=answer,
                factor=factor,
                start=start,
                end=end,
                sentences=split_sentences(answer.text),
                sources=(str(candidate.get("source", "NEURAL")),),
                confidence=float(candidate.get("model_confidence", 0)),
                candidate=candidate,
            )
            evidence.append(self.validator.validate(item, answer_text=answer.text, source_is_deterministic=False))
            sequence += 1
        return tuple(sorted(evidence, key=lambda item: (item.answer_id, item.character_start, item.factor_id)))

    @staticmethod
    def _aliases(factor: dict[str, Any]) -> tuple[str, ...]:
        return tuple(dict.fromkeys([str(factor.get("label", "")), *[str(item) for item in factor.get("aliases", [])]]))

    def _make_evidence(
        self,
        *,
        evidence_id: str,
        answer: AnswerInput,
        factor: dict[str, Any],
        start: int,
        end: int,
        sentences: tuple,
        sources: tuple[str, ...],
        confidence: float,
        candidate: dict[str, Any] | None = None,
    ) -> Evidence:
        span = answer.text[start:end] if 0 <= start <= end <= len(answer.text) else ""
        context = window(answer.text, start, end)
        entity_ids = tuple(str(item) for item in (candidate or {}).get("entity_ids", []) or [])
        if not entity_ids:
            entity_ids = self._detect_entities(context)
        nodes = self.nodes_by_factor.get(factor["factor_id"], [])
        scope = str((candidate or {}).get("scope") or self._infer_scope(factor, nodes, entity_ids, answer.target_entity_ids))
        if not entity_ids and scope == "STOCK" and answer.target_entity_ids:
            entity_ids = answer.target_entity_ids
        direction, negated = self._direction(context, factor, candidate)
        certainty = str((candidate or {}).get("certainty") or self._certainty(context))
        return Evidence(
            evidence_id=evidence_id,
            answer_id=answer.question_id,
            sentence_index=sentence_index_at(sentences, start),
            character_start=start,
            character_end=end,
            evidence_span=span,
            factor_id=factor["factor_id"],
            scope=scope,
            entity_ids=tuple(entity_ids),
            direction=direction,
            certainty=certainty,
            negated=negated,
            extractor_sources=sources,
            model_confidence=max(0.0, min(1.0, confidence)),
            validation_status="SCORE_ELIGIBLE",
            extractor_version=EXTRACTOR_VERSION,
        )

    def _detect_entities(self, text: str) -> tuple[str, ...]:
        detected = []
        for entity_id, aliases in self.entity_aliases.items():
            if any(re.search(re.escape(alias), text, re.IGNORECASE) for alias in aliases):
                detected.append(entity_id)
        return tuple(sorted(set(detected)))

    @staticmethod
    def _infer_scope(
        factor: dict[str, Any],
        nodes: list[dict[str, Any]],
        entity_ids: tuple[str, ...],
        target_entity_ids: tuple[str, ...],
    ) -> str:
        for node in nodes:
            if set(node.get("entity_ids", [])) & (set(entity_ids) | set(target_entity_ids)):
                return str(node.get("scope"))
        node_scopes = {str(node.get("scope")) for node in nodes}
        if len(node_scopes) == 1:
            return next(iter(node_scopes))
        entity_types = factor.get("entity_types", [])
        return str(entity_types[0] if entity_types else "INDUSTRY")

    @staticmethod
    def _direction(context: str, factor: dict[str, Any], candidate: dict[str, Any] | None) -> tuple[str, bool]:
        if candidate and candidate.get("direction"):
            return str(candidate["direction"]), bool(candidate.get("negated", False))
        patterns = factor.get("direction_patterns", {})
        positive = tuple(patterns.get("POSITIVE", [])) + POSITIVE_CUES
        negative = tuple(patterns.get("NEGATIVE", [])) + NEGATIVE_CUES
        negation_patterns = tuple(factor.get("negation_patterns", [])) + NEGATION_CUES
        negated = any(cue in context for cue in negation_patterns)
        pos = sum(context.count(cue) for cue in positive)
        neg = sum(context.count(cue) for cue in negative)
        if pos and neg:
            direction = "MIXED"
        elif neg > pos:
            direction = "NEGATIVE"
        elif pos:
            direction = "POSITIVE"
        else:
            direction = "CONDITIONAL"
        if negated and direction == "POSITIVE":
            direction = "NEGATIVE"
        return direction, negated

    @staticmethod
    def _certainty(context: str) -> str:
        if any(cue in context for cue in CONDITIONAL_CUES):
            return "CONDITIONAL"
        if any(cue in context for cue in LIKELY_CUES):
            return "LIKELY"
        return "ASSERTED"
