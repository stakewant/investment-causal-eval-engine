from __future__ import annotations

from collections import defaultdict
from typing import Any

from .contracts import Evidence, PathMatch, RelationEvidence

MATCHER_VERSION = "deterministic-segment-matcher-v0.2.0"


class GraphMatcher:
    def __init__(self, graph: dict[str, Any]) -> None:
        self.graph = graph
        self.nodes = {node["node_id"]: node for node in graph.get("nodes", [])}
        self.edges = {edge["edge_id"]: edge for edge in graph.get("edges", [])}

    def match(
        self,
        evidence: tuple[Evidence, ...],
        relations: tuple[RelationEvidence, ...],
    ) -> tuple[PathMatch, ...]:
        evidence_by_node = self._align_evidence(evidence)
        score_relations = [item for item in relations if item.validation_status == "SCORE_ELIGIBLE"]
        feedback_relations = [item for item in relations if item.validation_status == "FEEDBACK_ONLY"]
        results = []
        for path in self.graph.get("paths", []):
            results.append(
                self._match_path(path, evidence_by_node, score_relations, feedback_relations, evidence)
            )
        return tuple(results)

    def _align_evidence(self, evidence: tuple[Evidence, ...]) -> dict[str, list[Evidence]]:
        aligned: dict[str, list[Evidence]] = defaultdict(list)
        for node_id, node in self.nodes.items():
            for item in evidence:
                if item.validation_status != "SCORE_ELIGIBLE":
                    continue
                if item.factor_id != node.get("factor_id") or item.scope != node.get("scope"):
                    continue
                node_entities = set(node.get("entity_ids", []))
                if node.get("scope") == "STOCK" and item.entity_ids and not node_entities.intersection(item.entity_ids):
                    continue
                aligned[node_id].append(item)
        return aligned

    def _match_path(
        self,
        path: dict[str, Any],
        evidence_by_node: dict[str, list[Evidence]],
        score_relations: list[RelationEvidence],
        feedback_relations: list[RelationEvidence],
        all_evidence: tuple[Evidence, ...],
    ) -> PathMatch:
        if path.get("applicability") == "NOT_APPLICABLE":
            return PathMatch(
                path_id=path["path_id"],
                applicability="NOT_APPLICABLE",
                status="NOT_APPLICABLE",
                recognized_segment_ids=(),
                missing_segment_ids=(),
                recognized_node_ids=(),
                recognized_edge_ids=(),
                relation_evidence_ids=(),
                industry_to_stock_link="MISSING",
                diagnostic_tags=(),
                segment_coverage=0.0,
                target_entity_ids=tuple(path.get("target_entity_ids", [])),
            )

        path_node_ids = {item["node_id"] for item in path.get("path_nodes", [])}
        recognized_nodes = tuple(
            item["node_id"] for item in path.get("path_nodes", []) if evidence_by_node.get(item["node_id"])
        )
        recognized_segments: list[str] = []
        missing_segments: list[str] = []
        for segment in path.get("required_semantic_segments", []):
            target = recognized_segments if any(
                node_id in recognized_nodes for node_id in segment.get("one_of_node_ids", [])
            ) else missing_segments
            target.append(segment["segment_id"])

        recognized_edges: list[str] = []
        relation_ids: list[str] = []
        wrong_direction = False
        for relation in score_relations:
            for edge_id in relation.matched_edge_ids:
                if edge_id not in path.get("edge_ids", []):
                    continue
                edge = self.edges[edge_id]
                if edge.get("from_node") not in path_node_ids or edge.get("to_node") not in path_node_ids:
                    continue
                if self._sign_compatible(relation.sign, edge.get("sign")):
                    recognized_edges.append(edge_id)
                    relation_ids.append(relation.relation_evidence_id)
                else:
                    wrong_direction = True

        for node_id in recognized_nodes:
            node = self.nodes[node_id]
            for item in evidence_by_node[node_id]:
                if not self._sign_compatible(item.direction, node.get("expected_direction")):
                    wrong_direction = True

        required_segments = path.get("required_semantic_segments", [])
        coverage = len(recognized_segments) / len(required_segments) if required_segments else 1.0
        required_edge_ids = [
            edge_id
            for edge_id in path.get("edge_ids", [])
            if self.edges.get(edge_id, {}).get("importance") == "REQUIRED"
        ]
        all_required_edges = all(edge_id in recognized_edges for edge_id in required_edge_ids)
        disconnected = (
            len(recognized_nodes) >= 2
            and not all_required_edges
            and not recognized_edges
        )
        if wrong_direction:
            status = "WRONG_DIRECTION"
        elif coverage == 1.0 and all_required_edges:
            status = "COMPLETE"
        elif disconnected:
            status = "DISCONNECTED"
        elif recognized_nodes:
            status = "PARTIAL"
        else:
            status = "MISSING"

        link, link_tags = self._industry_stock_link(
            path, recognized_nodes, recognized_edges, feedback_relations, all_evidence
        )
        diagnostics = list(link_tags)
        if disconnected:
            diagnostics.append("FACTORS_LISTED_WITHOUT_RELATION")
        if wrong_direction:
            diagnostics.append("DIRECTION_CONFLICT")
        if missing_segments:
            diagnostics.extend(f"MISSING_SEGMENT:{item}" for item in missing_segments)
        return PathMatch(
            path_id=path["path_id"],
            applicability="APPLICABLE",
            status=status,
            recognized_segment_ids=tuple(recognized_segments),
            missing_segment_ids=tuple(missing_segments),
            recognized_node_ids=tuple(dict.fromkeys(recognized_nodes)),
            recognized_edge_ids=tuple(dict.fromkeys(recognized_edges)),
            relation_evidence_ids=tuple(dict.fromkeys(relation_ids)),
            industry_to_stock_link=link,
            diagnostic_tags=tuple(dict.fromkeys(diagnostics)),
            segment_coverage=round(coverage, 6),
            target_entity_ids=tuple(path.get("target_entity_ids", [])),
        )

    def _industry_stock_link(
        self,
        path: dict[str, Any],
        recognized_nodes: tuple[str, ...],
        recognized_edges: list[str],
        feedback_relations: list[RelationEvidence],
        all_evidence: tuple[Evidence, ...],
    ) -> tuple[str, tuple[str, ...]]:
        target_entities = set(path.get("target_entity_ids", []))
        exposure_nodes = [
            item["node_id"]
            for item in path.get("path_nodes", [])
            if item.get("path_node_role") == "DIRECT_EXPOSURE"
        ]
        recognized_exposure = [item for item in exposure_nodes if item in recognized_nodes]
        if not recognized_exposure:
            exposure_factor_ids = {
                self.nodes[node_id].get("factor_id") for node_id in exposure_nodes
            }
            explicit_wrong_entity = any(
                evidence.validation_status == "SCORE_ELIGIBLE"
                and evidence.factor_id in exposure_factor_ids
                and evidence.entity_ids
                and not target_entities.intersection(evidence.entity_ids)
                for evidence in all_evidence
            )
            return ("INVALID", ("TARGET_ENTITY_CONFLICT",)) if explicit_wrong_entity else ("MISSING", ())
        incoming_edges = [
            edge_id
            for edge_id in path.get("edge_ids", [])
            if self.edges.get(edge_id, {}).get("to_node") in recognized_exposure
        ]
        if any(edge_id in recognized_edges for edge_id in incoming_edges):
            return "VALID", ()
        feedback_edge_ids = {
            edge_id
            for relation in feedback_relations
            for edge_id in relation.matched_edge_ids
        }
        if any(edge_id in feedback_edge_ids for edge_id in incoming_edges):
            return "WEAK", ("IMPLICIT_INDUSTRY_STOCK_LINK",)
        return "WEAK", ("UNCONNECTED_TARGET_EXPOSURE",)

    @staticmethod
    def _sign_compatible(actual: str | None, expected: str | None) -> bool:
        if actual in {None, "MIXED", "CONDITIONAL"} or expected in {None, "MIXED", "CONDITIONAL"}:
            return True
        return actual == expected
