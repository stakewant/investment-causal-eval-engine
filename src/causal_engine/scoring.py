from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .contracts import DecisionInput, Evidence, PathMatch, RelationEvidence

M6_POLICY_VERSION = "m6-scoring-v1.1"
SCORER_VERSION = "m6-shadow-scorer-v0.2.0"

STATUS_RANK = {
    "COMPLETE": 5,
    "PARTIAL": 4,
    "WRONG_DIRECTION": 3,
    "DISCONNECTED": 2,
    "MISSING": 1,
    "NOT_APPLICABLE": 0,
}


def round_half_up(value: float, digits: int = 1) -> float:
    quantizer = Decimal("1").scaleb(-digits)
    return float(Decimal(str(value)).quantize(quantizer, rounding=ROUND_HALF_UP))


class M6Scorer:
    def __init__(self, graph: dict[str, Any]) -> None:
        self.graph = graph
        self.path_by_id = {item["path_id"]: item for item in graph.get("paths", [])}
        self.nodes = {item["node_id"]: item for item in graph.get("nodes", [])}

    def score(
        self,
        decision: DecisionInput,
        evidence: tuple[Evidence, ...],
        relations: tuple[RelationEvidence, ...],
        path_matches: tuple[PathMatch, ...],
    ) -> dict[str, Any]:
        applicable = [item for item in path_matches if item.applicability == "APPLICABLE"]
        if not applicable:
            return self._empty_result("NOT_APPLICABLE", path_matches)

        selected_entities = self._select_entities(decision, evidence, applicable)
        if not selected_entities:
            return self._empty_result("NOT_ASSESSED", path_matches)

        asset_results = []
        for entity_id, obligation_reason in selected_entities:
            entity_paths = [item for item in applicable if entity_id in item.target_entity_ids]
            if not entity_paths:
                continue
            asset_results.append(
                self._score_asset(
                    entity_id,
                    obligation_reason,
                    decision,
                    evidence,
                    relations,
                    entity_paths,
                )
            )
        scored_assets = [item for item in asset_results if item["status"] == "SCORED"]
        if not scored_assets:
            result = self._empty_result("NOT_ASSESSED", path_matches)
            result["asset_results"] = asset_results
            return result

        weights = [float(item.get("assessment_weight", 1.0)) for item in scored_assets]
        turn_score = sum(item["final_m6"] * weight for item, weight in zip(scored_assets, weights)) / sum(weights)
        components = self._aggregate_components(scored_assets, weights)
        links = [item["industry_to_stock_link"] for item in scored_assets]
        turn_link = min(links, key=lambda value: {"VALID": 3, "WEAK": 2, "MISSING": 1, "INVALID": 0}[value])
        return {
            "m6_policy_version": M6_POLICY_VERSION,
            "scorer_version": SCORER_VERSION,
            "status": "SCORED",
            "evaluation_mode": "SHADOW",
            "legacy_score_effect": 0,
            "components": components,
            "industry_context_diagnostic": self._industry_diagnostic(decision, path_matches),
            "industry_to_stock_link": turn_link,
            "base_m6": round_half_up(
                sum(item["base_m6"] * weight for item, weight in zip(scored_assets, weights)) / sum(weights)
            ),
            "caps_applied": self._union_caps(scored_assets),
            "final_m6": round_half_up(turn_score),
            "asset_results": asset_results,
            "path_matches": [item.to_dict() for item in path_matches],
            "exposure_weighted_diagnostic": self._exposure_diagnostic(decision, asset_results),
        }

    def _select_entities(
        self,
        decision: DecisionInput,
        evidence: tuple[Evidence, ...],
        paths: list[PathMatch],
    ) -> list[tuple[str, str]]:
        config = self.graph.get("m6_config", {})
        graph_targets = {entity for path in paths for entity in path.target_entity_ids}
        candidates: list[tuple[int, str, str]] = []
        for answer in decision.answers:
            for entity_id in answer.target_entity_ids:
                if entity_id in graph_targets and answer.requires_explanation:
                    candidates.append((0, entity_id, "QUESTION_REQUIRED"))
        for entity_id in config.get("required_entity_ids", []):
            if entity_id in graph_targets:
                candidates.append((0, entity_id, "TURN_POLICY_REQUIRED"))
        for item in evidence:
            if item.validation_status == "SCORE_ELIGIBLE" and item.scope == "STOCK":
                for entity_id in item.entity_ids:
                    if entity_id in graph_targets:
                        candidates.append((1, entity_id, "EXPLICIT_RATIONALE"))
        if config.get("require_largest_trade_explanation") and decision.orders:
            order = max(decision.orders, key=lambda item: item.absolute_notional)
            if order.entity_id in graph_targets and order.absolute_notional > 0:
                candidates.append((2, order.entity_id, "LARGEST_TRADE_POLICY"))
        ordered: list[tuple[str, str]] = []
        for _, entity_id, reason in sorted(candidates, key=lambda item: (item[0], item[1])):
            if entity_id not in {item[0] for item in ordered}:
                ordered.append((entity_id, reason))
        return ordered[: int(config.get("max_assets", 3))]

    def _score_asset(
        self,
        entity_id: str,
        obligation_reason: str,
        decision: DecisionInput,
        evidence: tuple[Evidence, ...],
        relations: tuple[RelationEvidence, ...],
        matches: list[PathMatch],
    ) -> dict[str, Any]:
        selected_matches = self._select_required_paths(matches)
        best = max(selected_matches, key=lambda item: (STATUS_RANK[item.status], item.segment_coverage))
        m2_dependency_failed = any(
            item.get("error_owner") == "M2" and "M6" in item.get("propagated_to", [])
            for item in decision.dependency_diagnostics
        )
        path_weights = [self._path_weight(item) for item in selected_matches]
        target_score = self._weighted(
            [self._target_exposure_score(item) for item in selected_matches], path_weights
        )
        transmission_score = self._weighted(
            [self._transmission_score(item, m2_dependency_failed) for item in selected_matches],
            path_weights,
        )
        config = self.graph.get("m6_config", {})
        component_weights = config.get("component_weights", {})
        target_weight = float(component_weights.get("target_exposure_reasoning", 0.5))
        transmission_weight = float(component_weights.get("causal_transmission_reasoning", 0.5))
        base = (
            target_score * target_weight + transmission_score * transmission_weight
        ) / max(0.000001, target_weight + transmission_weight)
        caps = self._caps(selected_matches, decision, evidence, relations, entity_id)
        cap_value = min((item["max_score"] for item in caps), default=5.0)
        final = round_half_up(max(1.0, min(5.0, base, cap_value)))
        return {
            "entity_id": entity_id,
            "status": "SCORED",
            "assessment_obligation": obligation_reason,
            "assessment_weight": 1.0,
            "selected_path_id": best.path_id,
            "selected_path_ids": [item.path_id for item in selected_matches],
            "components": {
                "target_exposure_reasoning": {
                    "status": "APPLICABLE",
                    "score": round_half_up(target_score),
                    "configured_weight": target_weight,
                },
                "causal_transmission_reasoning": {
                    "status": "APPLICABLE",
                    "score": round_half_up(transmission_score),
                    "configured_weight": transmission_weight,
                },
            },
            "industry_to_stock_link": min(
                (item.industry_to_stock_link for item in selected_matches),
                key=lambda value: {"VALID": 3, "WEAK": 2, "MISSING": 1, "INVALID": 0}[value],
            ),
            "base_m6": round_half_up(base),
            "caps_applied": caps,
            "final_m6": final,
            "diagnostic_tags": list(
                dict.fromkeys(tag for item in selected_matches for tag in item.diagnostic_tags)
            ),
            "dependency_failed_m2": m2_dependency_failed,
        }

    @staticmethod
    def _target_exposure_score(match: PathMatch) -> float:
        if match.industry_to_stock_link == "INVALID":
            return 1.0
        if match.industry_to_stock_link == "MISSING":
            return 2.0
        target_recognized = "TARGET_EXPOSURE" in match.recognized_segment_ids
        outcome_recognized = "TARGET_OUTCOME" in match.recognized_segment_ids
        if match.industry_to_stock_link == "VALID" and target_recognized and outcome_recognized:
            return 5.0 if match.status == "COMPLETE" else 4.0
        if target_recognized:
            return 3.0
        return 2.0

    @staticmethod
    def _transmission_score(match: PathMatch, m2_dependency_failed: bool) -> float:
        if match.status == "COMPLETE":
            return 5.0
        if match.status == "WRONG_DIRECTION" and m2_dependency_failed:
            return max(3.0, 2.0 + 3.0 * match.segment_coverage)
        if match.status == "WRONG_DIRECTION":
            return 1.0
        if match.status == "DISCONNECTED":
            return 2.0
        if match.status == "PARTIAL":
            return max(2.0, min(4.0, 2.0 + 2.0 * match.segment_coverage))
        return 1.0

    def _caps(
        self,
        matches: list[PathMatch],
        decision: DecisionInput,
        evidence: tuple[Evidence, ...],
        relations: tuple[RelationEvidence, ...],
        entity_id: str,
    ) -> list[dict[str, Any]]:
        caps: list[dict[str, Any]] = []
        links = {match.industry_to_stock_link for match in matches}
        if "INVALID" in links:
            caps.append({"policy_id": "M6-CAP-TARGET-FALSE-01", "max_score": 2.5, "evidence_ids": []})
        elif "WEAK" in links:
            caps.append({"policy_id": "M6-CAP-SCOPE-WEAK-01", "max_score": 3.5, "evidence_ids": []})
        elif "MISSING" in links:
            caps.append({"policy_id": "M6-CAP-SCOPE-MISSING-01", "max_score": 3.0, "evidence_ids": []})
        disconnected = [match for match in matches if match.status == "DISCONNECTED"]
        if disconnected:
            relevant_ids = [
                item.evidence_id
                for item in evidence
                if item.validation_status == "SCORE_ELIGIBLE"
                and (item.scope != "STOCK" or not item.entity_ids or entity_id in item.entity_ids)
            ]
            caps.append(
                {
                    "policy_id": "M6-CAP-LIST-ONLY-01",
                    "max_score": 3.0,
                    "evidence_ids": relevant_ids,
                }
            )
        relevant_answers = [
            answer for answer in decision.answers if entity_id in answer.target_entity_ids or not answer.target_entity_ids
        ]
        rationale = " ".join(answer.text.strip() for answer in relevant_answers if answer.text.strip())
        relevant_evidence = [
            item
            for item in evidence
            if item.validation_status == "SCORE_ELIGIBLE"
            and (item.scope != "STOCK" or not item.entity_ids or entity_id in item.entity_ids)
        ]
        relevant_evidence_ids = {item.evidence_id for item in relevant_evidence}
        relevant_relations = [
            item
            for item in relations
            if item.validation_status == "SCORE_ELIGIBLE"
            and item.source_evidence_id in relevant_evidence_ids
            and item.target_evidence_id in relevant_evidence_ids
        ]
        if len(rationale.replace(" ", "")) < 12 or not relevant_evidence:
            caps.append({"policy_id": "M6-CAP-INSUFFICIENT-INPUT-01", "max_score": 2.0, "evidence_ids": []})
        elif len(relevant_evidence) < 2 or not relevant_relations:
            caps.append({"policy_id": "M6-CAP-WEAK-INPUT-01", "max_score": 3.5, "evidence_ids": [item.evidence_id for item in relevant_evidence]})
        return caps

    def _select_required_paths(self, matches: list[PathMatch]) -> list[PathMatch]:
        required = [
            match
            for match in matches
            if self.path_by_id[match.path_id].get("importance") == "REQUIRED"
        ]
        candidates = required or matches
        grouped: dict[str, list[PathMatch]] = defaultdict(list)
        singles: list[PathMatch] = []
        for match in candidates:
            group_id = self.path_by_id[match.path_id].get("alternative_group_id")
            if group_id:
                grouped[str(group_id)].append(match)
            else:
                singles.append(match)
        selected = singles[:]
        for alternatives in grouped.values():
            selected.append(
                max(alternatives, key=lambda item: (STATUS_RANK[item.status], item.segment_coverage))
            )
        return selected

    def _path_weight(self, match: PathMatch) -> float:
        path_class = self.path_by_id[match.path_id].get("path_class")
        configured = self.graph.get("m6_config", {}).get("path_class_weights", {})
        return max(0.0, float(configured.get(path_class, 1.0)))

    @staticmethod
    def _weighted(values: list[float], weights: list[float]) -> float:
        total = sum(weights)
        if total <= 0:
            return sum(values) / len(values)
        return sum(value * weight for value, weight in zip(values, weights)) / total

    @staticmethod
    def _aggregate_components(assets: list[dict[str, Any]], weights: list[float]) -> dict[str, Any]:
        result = {}
        for name in ("target_exposure_reasoning", "causal_transmission_reasoning"):
            values = [item["components"][name] for item in assets]
            result[name] = {
                "status": "APPLICABLE",
                "score": round_half_up(sum(value["score"] * weight for value, weight in zip(values, weights)) / sum(weights)),
                "configured_weight": values[0]["configured_weight"],
            }
        return result

    @staticmethod
    def _union_caps(assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique = {}
        for asset in assets:
            for cap in asset["caps_applied"]:
                unique[(cap["policy_id"], cap["max_score"])] = cap
        return list(unique.values())

    @staticmethod
    def _industry_diagnostic(decision: DecisionInput, matches: tuple[PathMatch, ...]) -> dict[str, Any]:
        dependency = [
            item for item in decision.dependency_diagnostics if item.get("error_owner") in {"M1", "M2", "M3"}
        ]
        has_industry = any("INDUSTRY_TRANSMISSION" in item.recognized_segment_ids for item in matches)
        return {
            "status": "DEPENDENCY_REPORTED" if dependency else ("RECOGNIZED" if has_industry else "MISSING"),
            "score_effect": 0,
            "propagated_diagnostics": dependency,
        }

    @staticmethod
    def _exposure_diagnostic(decision: DecisionInput, assets: list[dict[str, Any]]) -> dict[str, Any]:
        unsupported = {item["entity_id"] for item in assets if item.get("final_m6", 5) <= 2.5}
        order_notional = defaultdict(float)
        for order in decision.orders:
            order_notional[order.entity_id] += order.absolute_notional
        total = sum(order_notional.values())
        ratio = sum(value for entity, value in order_notional.items() if entity in unsupported) / total if total else 0.0
        risk = "HIGH" if ratio >= 0.5 else "MEDIUM" if ratio >= 0.2 else "LOW"
        return {"risk_level": risk, "unsupported_exposure_ratio": round(ratio, 4), "score_effect": 0}

    @staticmethod
    def _empty_result(status: str, paths: tuple[PathMatch, ...]) -> dict[str, Any]:
        return {
            "m6_policy_version": M6_POLICY_VERSION,
            "scorer_version": SCORER_VERSION,
            "status": status,
            "evaluation_mode": "SHADOW",
            "legacy_score_effect": 0,
            "path_matches": [item.to_dict() for item in paths],
            "asset_results": [],
        }
