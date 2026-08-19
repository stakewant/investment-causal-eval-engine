from __future__ import annotations

from typing import Any

from .contracts import FeedbackItem, PathMatch

FEEDBACK_PLANNER_VERSION = "feedback-planner-v0.2.0"
FEEDBACK_RENDERER_VERSION = "ko-template-renderer-v0.2.0"

TEMPLATES = {
    "complete": "산업 요인에서 선택 종목의 실제 노출과 결과까지의 연결을 구체적으로 설명했습니다.",
    "partial": "핵심 방향은 잡았지만 {missing} 구간의 연결 근거가 더 필요합니다.",
    "disconnected": "관련 요인은 찾았지만 요인 사이에 왜 영향이 전달되는지 설명하지 않았습니다.",
    "wrong_direction": "영향 경로의 방향이 기준 근거와 충돌합니다. 원인과 결과의 방향을 다시 확인해 보세요.",
    "missing": "산업 변화가 선택 종목의 사업·매출·비용 중 어디에 닿는지 연결해 보세요.",
    "not_applicable": "이번 턴에는 이 경로가 평가 대상이 아닙니다.",
    "fallback": "인식한 요인과 선택 종목 사이의 전달 경로를 한 단계씩 설명해 보세요.",
}


class FeedbackPlanner:
    def __init__(self, factor_catalog: dict[str, Any], source_claims: dict[str, Any], graph: dict[str, Any]) -> None:
        self.factors = {item["factor_id"]: item for item in factor_catalog.get("factors", [])}
        self.source_claims = source_claims
        self.claims = {item["claim_id"]: item for item in source_claims.get("claims", [])}
        self.graph = graph
        self.paths = {item["path_id"]: item for item in graph.get("paths", [])}
        self.nodes = {item["node_id"]: item for item in graph.get("nodes", [])}
        self.edges = {item["edge_id"]: item for item in graph.get("edges", [])}

    def plan(self, matches: tuple[PathMatch, ...]) -> dict[str, Any]:
        items: list[FeedbackItem] = []
        for match in matches:
            path = self.paths[match.path_id]
            claim_ids = self._allowed_claims(path)
            if match.status == "COMPLETE":
                code, severity, key = "PATH_COMPLETE", "SUCCESS", "complete"
            elif match.status == "PARTIAL":
                code, severity, key = "PATH_PARTIAL", "WARNING", "partial"
            elif match.status == "DISCONNECTED":
                code, severity, key = "PATH_DISCONNECTED", "WARNING", "disconnected"
            elif match.status == "WRONG_DIRECTION":
                code, severity, key = "PATH_WRONG_DIRECTION", "ERROR", "wrong_direction"
            elif match.status == "NOT_APPLICABLE":
                code, severity, key = "PATH_NOT_APPLICABLE", "INFO", "not_applicable"
            else:
                code, severity, key = "PATH_MISSING", "INFO", "missing"
            items.append(
                FeedbackItem(
                    code=code,
                    severity=severity,  # type: ignore[arg-type]
                    path_id=match.path_id,
                    entity_ids=match.target_entity_ids,
                    segment_ids=match.missing_segment_ids,
                    claim_ids=claim_ids,
                    template_key=key,
                    parameters={"missing": ", ".join(match.missing_segment_ids)},
                )
            )
        plan = {
            "planner_version": FEEDBACK_PLANNER_VERSION,
            "information_cutoff_at": self.graph.get("information_cutoff_at"),
            "items": [item.to_dict() for item in items],
        }
        return OutputValidator(self.source_claims, self.graph).validate_plan(plan)

    def _allowed_claims(self, path: dict[str, Any]) -> tuple[str, ...]:
        if path.get("feedback_release") != "POST_TURN_AS_OF":
            return ()
        references: set[str] = set()
        for item in path.get("path_nodes", []):
            references.update(self.nodes.get(item["node_id"], {}).get("source_claim_refs", []))
        for edge_id in path.get("edge_ids", []):
            references.update(self.edges.get(edge_id, {}).get("source_claim_refs", []))
        return tuple(
            sorted(
                claim_id
                for claim_id in references
                if self.claims.get(claim_id, {}).get("knowledge_role") == "AS_OF_EVIDENCE"
                and self.claims.get(claim_id, {}).get("public_status") == "PUBLIC_AS_OF"
                and "POST_TURN_FEEDBACK" in self.claims.get(claim_id, {}).get("allowed_uses", [])
            )
        )


class OutputValidator:
    VERSION = "output-validator-v0.2.0"

    def __init__(self, source_claims: dict[str, Any], graph: dict[str, Any]) -> None:
        self.claims = {item["claim_id"]: item for item in source_claims.get("claims", [])}
        self.paths = {item["path_id"]: item for item in graph.get("paths", [])}
        self.allowed_entities = {
            entity_id for node in graph.get("nodes", []) for entity_id in node.get("entity_ids", [])
        }

    def validate_plan(self, plan: dict[str, Any]) -> dict[str, Any]:
        violations: list[str] = []
        for index, item in enumerate(plan.get("items", [])):
            path = self.paths.get(item.get("path_id"))
            if path is None:
                violations.append(f"items[{index}].path_id")
                continue
            path_segments = {segment["segment_id"] for segment in path.get("required_semantic_segments", [])}
            if not set(item.get("segment_ids", [])).issubset(path_segments):
                violations.append(f"items[{index}].segment_ids")
            if not set(item.get("entity_ids", [])).issubset(self.allowed_entities):
                violations.append(f"items[{index}].entity_ids")
            for claim_id in item.get("claim_ids", []):
                claim = self.claims.get(claim_id, {})
                if (
                    claim.get("knowledge_role") != "AS_OF_EVIDENCE"
                    or claim.get("public_status") != "PUBLIC_AS_OF"
                    or "POST_TURN_FEEDBACK" not in claim.get("allowed_uses", [])
                ):
                    violations.append(f"items[{index}].claim_ids:{claim_id}")
        if violations:
            return {
                "planner_version": plan.get("planner_version"),
                "information_cutoff_at": plan.get("information_cutoff_at"),
                "validation_status": "TEMPORAL_OUTPUT_REJECTED",
                "violations": violations,
                "items": [
                    FeedbackItem(
                        code="SAFE_FALLBACK",
                        severity="INFO",
                        path_id=None,
                        entity_ids=(),
                        segment_ids=(),
                        claim_ids=(),
                        template_key="fallback",
                    ).to_dict()
                ],
            }
        return {**plan, "validation_status": "ACCEPTED", "violations": []}


class KoreanTemplateRenderer:
    def render(self, plan: dict[str, Any]) -> dict[str, Any]:
        messages = []
        for item in plan.get("items", []):
            template = TEMPLATES.get(item.get("template_key"), TEMPLATES["fallback"])
            try:
                message = template.format(**item.get("parameters", {}))
            except (KeyError, ValueError):
                message = TEMPLATES["fallback"]
            messages.append({"code": item.get("code"), "severity": item.get("severity"), "text": message})
        return {
            "renderer_version": FEEDBACK_RENDERER_VERSION,
            "validation_status": plan.get("validation_status"),
            "messages": messages,
        }
