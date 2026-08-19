from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .errors import CompileIssue, GraphCompileError

COMPILER_VERSION = "graph-compiler-v0.2.0"

KNOWLEDGE_ROLES = {
    "AS_OF_EVIDENCE",
    "RETROSPECTIVE_ANALYSIS",
    "OUTCOME_EVIDENCE",
}
IMPORTANCE_VALUES = {"REQUIRED", "SUPPORTING", "OPTIONAL"}
SCORING_ELIGIBILITY_VALUES = {
    "MANDATORY_ELIGIBLE",
    "OPTIONAL_ELIGIBLE",
    "FEEDBACK_ONLY",
    "INELIGIBLE",
}
PATH_APPLICABILITY_VALUES = {"APPLICABLE", "NOT_APPLICABLE"}
FEEDBACK_RELEASE_VALUES = {"POST_TURN_AS_OF", "FINAL_REVIEW_ONLY"}


def load_json(path: str | Path) -> dict[str, Any]:
    resolved = Path(path)
    with resolved.open("r", encoding="utf-8-sig") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {resolved}")
    return value


def _parse_datetime(value: Any, *, field_path: str, issues: list[CompileIssue]) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        issues.append(CompileIssue("E_DATETIME", field_path, "ISO-8601 timestamp is required"))
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            issues.append(CompileIssue("E_DATETIME_TZ", field_path, "timezone offset is required"))
            return None
        return parsed
    except ValueError:
        issues.append(CompileIssue("E_DATETIME", field_path, f"invalid ISO-8601 timestamp: {value}"))
        return None


def _index_by_id(
    items: Any,
    *,
    id_field: str,
    collection_path: str,
    issues: list[CompileIssue],
) -> dict[str, dict[str, Any]]:
    if not isinstance(items, list):
        issues.append(CompileIssue("E_TYPE", collection_path, "must be an array"))
        return {}

    indexed: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(items):
        path = f"{collection_path}[{index}]"
        if not isinstance(item, dict):
            issues.append(CompileIssue("E_TYPE", path, "must be an object"))
            continue
        item_id = item.get(id_field)
        if not isinstance(item_id, str) or not item_id.strip():
            issues.append(CompileIssue("E_REQUIRED_FIELD", f"{path}.{id_field}", "non-empty string required"))
            continue
        if item_id in indexed:
            issues.append(CompileIssue("E_DUPLICATE_ID", f"{path}.{id_field}", f"duplicate id: {item_id}"))
            continue
        indexed[item_id] = item
    return indexed


def _canonical_hash(*objects: dict[str, Any]) -> str:
    payload = json.dumps(objects, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


class GraphCompiler:
    """Compile an authored turn graph into a reproducible shadow-evaluation artifact."""

    def __init__(
        self,
        *,
        factor_catalog: dict[str, Any],
        source_claims: dict[str, Any],
        graph: dict[str, Any],
    ) -> None:
        self.factor_catalog = factor_catalog
        self.source_claims = source_claims
        self.graph = graph
        self.issues: list[CompileIssue] = []
        self.warnings: list[CompileIssue] = []

    def compile(self) -> dict[str, Any]:
        self.issues = []
        self.warnings = []

        cutoff = _parse_datetime(
            self.graph.get("information_cutoff_at"),
            field_path="graph.information_cutoff_at",
            issues=self.issues,
        )

        factors = self._validate_factor_catalog()
        claims = self._validate_source_claims(cutoff)
        nodes = self._validate_nodes(factors, claims, cutoff)
        edges = self._validate_edges(nodes, claims, cutoff)
        paths = self._validate_paths(factors, claims, nodes, edges)
        self._validate_graph_contract(nodes, paths)

        if self.issues:
            raise GraphCompileError(self.issues)

        compile_hash = _canonical_hash(self.factor_catalog, self.source_claims, self.graph)
        return {
            "compiler_version": COMPILER_VERSION,
            "graph_compile_hash": compile_hash,
            "scenario_id": self.graph["scenario_id"],
            "scenario_version": self.graph["scenario_version"],
            "turn_no": self.graph["turn_no"],
            "source_policy_version": self.graph["source_policy_version"],
            "graph_schema_version": self.graph["schema_version"],
            "graph_version": self.graph["graph_version"],
            "warning_count": len(self.warnings),
            "warnings": [warning.__dict__ for warning in self.warnings],
            "normalized_graph": self.graph,
        }

    def _validate_factor_catalog(self) -> dict[str, dict[str, Any]]:
        entities = _index_by_id(
            self.factor_catalog.get("entities", []),
            id_field="entity_id",
            collection_path="factor_catalog.entities",
            issues=self.issues,
        )
        self._entity_ids = set(entities)
        factors = _index_by_id(
            self.factor_catalog.get("factors"),
            id_field="factor_id",
            collection_path="factor_catalog.factors",
            issues=self.issues,
        )
        alias_owners: dict[str, set[str]] = {}
        for factor_id, factor in factors.items():
            path = f"factor_catalog.factors[{factor_id}]"
            roles = factor.get("allowed_roles")
            if not isinstance(roles, list) or not roles or not all(isinstance(role, str) for role in roles):
                self.issues.append(CompileIssue("E_ALLOWED_ROLES", f"{path}.allowed_roles", "non-empty string array required"))
            for alias in [factor.get("label"), *factor.get("aliases", [])]:
                if isinstance(alias, str) and alias.strip():
                    alias_owners.setdefault(alias.casefold().replace(" ", ""), set()).add(factor_id)
        for alias, owners in alias_owners.items():
            if len(owners) > 1:
                self.warnings.append(
                    CompileIssue("W_AMBIGUOUS_ALIAS", "factor_catalog.factors", f"alias {alias!r} belongs to {sorted(owners)}")
                )
        return factors

    def _validate_source_claims(self, cutoff: datetime | None) -> dict[str, dict[str, Any]]:
        claims = _index_by_id(
            self.source_claims.get("claims"),
            id_field="claim_id",
            collection_path="source_claims.claims",
            issues=self.issues,
        )
        for claim_id, claim in claims.items():
            path = f"source_claims.claims[{claim_id}]"
            role = claim.get("knowledge_role")
            if role not in KNOWLEDGE_ROLES:
                self.issues.append(CompileIssue("E_KNOWLEDGE_ROLE", f"{path}.knowledge_role", f"unsupported role: {role}"))

            eligibility = claim.get("scoring_eligibility")
            if eligibility not in SCORING_ELIGIBILITY_VALUES:
                self.issues.append(CompileIssue("E_SCORING_ELIGIBILITY", f"{path}.scoring_eligibility", f"unsupported value: {eligibility}"))

            available_at = _parse_datetime(
                claim.get("available_at"),
                field_path=f"{path}.available_at",
                issues=self.issues,
            )
            if (
                cutoff is not None
                and available_at is not None
                and available_at > cutoff
                and claim.get("public_status") == "PUBLIC_AS_OF"
            ):
                self.issues.append(
                    CompileIssue(
                        "E_PUBLIC_STATUS_CONTRADICTION",
                        f"{path}.public_status",
                        "claim is marked PUBLIC_AS_OF but becomes available after the cutoff",
                    )
                )

            if eligibility == "MANDATORY_ELIGIBLE":
                self._validate_mandatory_claim(claim_id, claim, cutoff, available_at)
        return claims

    def _validate_mandatory_claim(
        self,
        claim_id: str,
        claim: dict[str, Any],
        cutoff: datetime | None,
        available_at: datetime | None,
    ) -> None:
        path = f"source_claims.claims[{claim_id}]"
        if claim.get("knowledge_role") != "AS_OF_EVIDENCE":
            self.issues.append(CompileIssue("E_MANDATORY_ROLE", path, "mandatory claim must be AS_OF_EVIDENCE"))
        if claim.get("public_status") != "PUBLIC_AS_OF":
            self.issues.append(CompileIssue("E_MANDATORY_PUBLIC", path, "mandatory claim must be PUBLIC_AS_OF"))
        if cutoff is not None and available_at is not None and available_at > cutoff:
            self.issues.append(CompileIssue("E_TEMPORAL_LEAKAGE", path, "mandatory claim is available after the cutoff"))

        if claim.get("visibility_status") == "VISIBLE_TO_USER":
            return

        prior = claim.get("prior_knowledge")
        if not isinstance(prior, dict) or prior.get("status") != "APPROVED":
            self.issues.append(
                CompileIssue(
                    "E_MANDATORY_VISIBILITY",
                    path,
                    "mandatory claim must be visible or approved prior knowledge",
                )
            )
            return

        reviewers = prior.get("reviewers")
        reviewer_ids = {
            reviewer.get("reviewer_id")
            for reviewer in reviewers or []
            if isinstance(reviewer, dict) and reviewer.get("reviewer_id")
        }
        if len(reviewer_ids) < 2:
            self.issues.append(CompileIssue("E_PRIOR_REVIEW", f"{path}.prior_knowledge.reviewers", "two distinct reviewers required"))
        if not prior.get("policy_rule_id") or not prior.get("justification_text"):
            self.issues.append(CompileIssue("E_PRIOR_JUSTIFICATION", f"{path}.prior_knowledge", "policy_rule_id and justification_text required"))

    def _validate_nodes(
        self,
        factors: dict[str, dict[str, Any]],
        claims: dict[str, dict[str, Any]],
        cutoff: datetime | None,
    ) -> dict[str, dict[str, Any]]:
        del cutoff
        nodes = _index_by_id(
            self.graph.get("nodes"),
            id_field="node_id",
            collection_path="graph.nodes",
            issues=self.issues,
        )
        for node_id, node in nodes.items():
            path = f"graph.nodes[{node_id}]"
            factor_id = node.get("factor_id")
            if factor_id not in factors:
                self.issues.append(CompileIssue("E_UNKNOWN_FACTOR", f"{path}.factor_id", f"unknown factor: {factor_id}"))
            elif node.get("scope") not in factors[factor_id].get("entity_types", []):
                self.issues.append(CompileIssue("E_FACTOR_SCOPE", f"{path}.scope", f"scope is not allowed by factor {factor_id}"))
            if "role" in node:
                self.issues.append(CompileIssue("E_FIXED_NODE_ROLE", f"{path}.role", "role belongs to path_nodes, not graph nodes"))
            if node.get("importance") not in IMPORTANCE_VALUES:
                self.issues.append(CompileIssue("E_IMPORTANCE", f"{path}.importance", "unsupported importance"))
            if node.get("scope") == "STOCK" and not node.get("entity_ids"):
                self.issues.append(CompileIssue("E_STOCK_ENTITY", f"{path}.entity_ids", "stock node requires at least one entity id"))
            unknown_entities = set(node.get("entity_ids", [])) - getattr(self, "_entity_ids", set())
            if unknown_entities:
                self.issues.append(CompileIssue("E_UNKNOWN_ENTITY", f"{path}.entity_ids", f"unknown entities: {sorted(unknown_entities)}"))
            self._validate_claim_refs(path, node.get("source_claim_refs"), claims)
            if node.get("importance") == "REQUIRED" and not self._has_mandatory_claim(node.get("source_claim_refs"), claims):
                self.issues.append(CompileIssue("E_REQUIRED_EVIDENCE", path, "required node needs at least one mandatory-eligible claim"))
        return nodes

    def _validate_edges(
        self,
        nodes: dict[str, dict[str, Any]],
        claims: dict[str, dict[str, Any]],
        cutoff: datetime | None,
    ) -> dict[str, dict[str, Any]]:
        edges = _index_by_id(
            self.graph.get("edges"),
            id_field="edge_id",
            collection_path="graph.edges",
            issues=self.issues,
        )
        for edge_id, edge in edges.items():
            path = f"graph.edges[{edge_id}]"
            if edge.get("from_node") not in nodes:
                self.issues.append(CompileIssue("E_UNKNOWN_NODE", f"{path}.from_node", f"unknown node: {edge.get('from_node')}"))
            if edge.get("to_node") not in nodes:
                self.issues.append(CompileIssue("E_UNKNOWN_NODE", f"{path}.to_node", f"unknown node: {edge.get('to_node')}"))
            if edge.get("importance") not in IMPORTANCE_VALUES:
                self.issues.append(CompileIssue("E_IMPORTANCE", f"{path}.importance", "unsupported importance"))

            self._validate_claim_refs(path, edge.get("source_claim_refs"), claims)
            if edge.get("importance") == "REQUIRED" and not self._has_mandatory_claim(edge.get("source_claim_refs"), claims):
                self.issues.append(CompileIssue("E_REQUIRED_EVIDENCE", path, "required edge needs at least one mandatory-eligible claim"))

            evidence_available_at = _parse_datetime(
                edge.get("evidence_available_at"),
                field_path=f"{path}.evidence_available_at",
                issues=self.issues,
            )
            valid_from = _parse_datetime(
                edge.get("valid_from"),
                field_path=f"{path}.valid_from",
                issues=self.issues,
            )
            valid_to = None
            if edge.get("valid_to") is not None:
                valid_to = _parse_datetime(
                    edge.get("valid_to"),
                    field_path=f"{path}.valid_to",
                    issues=self.issues,
                )
            if cutoff is not None:
                if evidence_available_at is not None and evidence_available_at > cutoff and edge.get("importance") == "REQUIRED":
                    self.issues.append(CompileIssue("E_TEMPORAL_LEAKAGE", path, "required edge evidence is available after cutoff"))
                if valid_from is not None and valid_from > cutoff and edge.get("importance") == "REQUIRED":
                    self.issues.append(CompileIssue("E_EDGE_NOT_YET_VALID", path, "required edge is not valid at cutoff"))
                if valid_to is not None and valid_to < cutoff and edge.get("importance") == "REQUIRED":
                    self.issues.append(CompileIssue("E_EDGE_EXPIRED", path, "required edge expired before cutoff"))
            if valid_from is not None and valid_to is not None and valid_to < valid_from:
                self.issues.append(CompileIssue("E_INVALID_VALIDITY_RANGE", path, "valid_to precedes valid_from"))
            if edge.get("temporal_status") == "PUBLIC_AS_OF" and evidence_available_at is not None and cutoff is not None and evidence_available_at > cutoff:
                self.issues.append(CompileIssue("E_PUBLIC_STATUS_CONTRADICTION", f"{path}.temporal_status", "edge is marked PUBLIC_AS_OF after cutoff"))
        return edges

    def _validate_paths(
        self,
        factors: dict[str, dict[str, Any]],
        claims: dict[str, dict[str, Any]],
        nodes: dict[str, dict[str, Any]],
        edges: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        paths = _index_by_id(
            self.graph.get("paths"),
            id_field="path_id",
            collection_path="graph.paths",
            issues=self.issues,
        )
        for path_id, path_value in paths.items():
            path = f"graph.paths[{path_id}]"
            applicability = path_value.get("applicability")
            if applicability not in PATH_APPLICABILITY_VALUES:
                self.issues.append(CompileIssue("E_APPLICABILITY", f"{path}.applicability", "unsupported applicability"))
            if applicability == "NOT_APPLICABLE" and path_value.get("importance") == "REQUIRED":
                self.issues.append(CompileIssue("E_NOT_APPLICABLE_REQUIRED", path, "NOT_APPLICABLE path cannot be REQUIRED"))

            feedback_release = path_value.get("feedback_release")
            if feedback_release not in FEEDBACK_RELEASE_VALUES:
                self.issues.append(CompileIssue("E_FEEDBACK_RELEASE", f"{path}.feedback_release", "unsupported feedback release"))

            path_nodes = path_value.get("path_nodes")
            if not isinstance(path_nodes, list) or not path_nodes:
                self.issues.append(CompileIssue("E_PATH_NODES", f"{path}.path_nodes", "non-empty path node array required"))
                continue

            ordered = sorted(path_nodes, key=lambda item: item.get("sequence", -1) if isinstance(item, dict) else -1)
            sequences = [item.get("sequence") for item in ordered if isinstance(item, dict)]
            if sequences != list(range(1, len(ordered) + 1)):
                self.issues.append(CompileIssue("E_PATH_SEQUENCE", f"{path}.path_nodes", "sequence must be contiguous and start at 1"))

            ordered_node_ids: list[str] = []
            for index, path_node in enumerate(ordered):
                node_path = f"{path}.path_nodes[{index}]"
                if not isinstance(path_node, dict):
                    self.issues.append(CompileIssue("E_TYPE", node_path, "must be an object"))
                    continue
                node_id = path_node.get("node_id")
                ordered_node_ids.append(node_id)
                node = nodes.get(node_id)
                if node is None:
                    self.issues.append(CompileIssue("E_UNKNOWN_NODE", f"{node_path}.node_id", f"unknown node: {node_id}"))
                    continue
                factor = factors.get(node.get("factor_id"), {})
                role = path_node.get("path_node_role")
                if role not in factor.get("allowed_roles", []):
                    self.issues.append(
                        CompileIssue(
                            "E_ROLE_NOT_ALLOWED",
                            f"{node_path}.path_node_role",
                            f"role {role} is not allowed for factor {node.get('factor_id')}",
                        )
                    )

            if len(ordered_node_ids) != len(set(ordered_node_ids)):
                self.issues.append(CompileIssue("E_PATH_CYCLE", f"{path}.path_nodes", "path cannot repeat a node"))

            path_edge_ids = path_value.get("edge_ids")
            if not isinstance(path_edge_ids, list):
                self.issues.append(CompileIssue("E_PATH_EDGES", f"{path}.edge_ids", "must be an array"))
                path_edge_ids = []
            selected_edges = []
            for edge_id in path_edge_ids:
                edge = edges.get(edge_id)
                if edge is None:
                    self.issues.append(CompileIssue("E_UNKNOWN_EDGE", f"{path}.edge_ids", f"unknown edge: {edge_id}"))
                else:
                    selected_edges.append(edge)

            for from_node, to_node in zip(ordered_node_ids, ordered_node_ids[1:]):
                if not any(edge.get("from_node") == from_node and edge.get("to_node") == to_node for edge in selected_edges):
                    self.issues.append(
                        CompileIssue(
                            "E_PATH_DISCONNECTED",
                            f"{path}.edge_ids",
                            f"missing path edge from {from_node} to {to_node}",
                        )
                    )

            segments = path_value.get("required_semantic_segments")
            if not isinstance(segments, list):
                self.issues.append(CompileIssue("E_SEGMENTS", f"{path}.required_semantic_segments", "must be an array"))
                segments = []
            if len(segments) > 4:
                self.issues.append(CompileIssue("E_TOO_MANY_SEGMENTS", f"{path}.required_semantic_segments", "at most four required segments are allowed"))
            segment_ids: set[str] = set()
            for index, segment in enumerate(segments):
                segment_path = f"{path}.required_semantic_segments[{index}]"
                if not isinstance(segment, dict):
                    self.issues.append(CompileIssue("E_TYPE", segment_path, "must be an object"))
                    continue
                segment_id = segment.get("segment_id")
                if segment_id in segment_ids:
                    self.issues.append(CompileIssue("E_DUPLICATE_SEGMENT", f"{segment_path}.segment_id", f"duplicate segment: {segment_id}"))
                segment_ids.add(segment_id)
                alternatives = segment.get("one_of_node_ids")
                if not isinstance(alternatives, list) or not alternatives:
                    self.issues.append(CompileIssue("E_SEGMENT_ALTERNATIVES", f"{segment_path}.one_of_node_ids", "non-empty array required"))
                elif not any(node_id in ordered_node_ids for node_id in alternatives):
                    self.issues.append(CompileIssue("E_SEGMENT_OUTSIDE_PATH", segment_path, "segment must reference at least one node in the path"))

            if feedback_release == "POST_TURN_AS_OF":
                referenced_claim_ids: set[str] = set()
                for node_id in ordered_node_ids:
                    referenced_claim_ids.update(nodes.get(node_id, {}).get("source_claim_refs", []))
                for edge in selected_edges:
                    referenced_claim_ids.update(edge.get("source_claim_refs", []))
                for claim_id in referenced_claim_ids:
                    claim = claims.get(claim_id)
                    if claim and (
                        claim.get("knowledge_role") != "AS_OF_EVIDENCE"
                        or claim.get("public_status") != "PUBLIC_AS_OF"
                    ):
                        self.issues.append(
                            CompileIssue(
                                "E_POST_TURN_FUTURE_INFO",
                                path,
                                f"POST_TURN_AS_OF path references non-as-of claim: {claim_id}",
                            )
                        )
                    if claim and "POST_TURN_FEEDBACK" not in claim.get("allowed_uses", []):
                        self.issues.append(
                            CompileIssue(
                                "E_FEEDBACK_USE_NOT_ALLOWED",
                                path,
                                f"claim does not allow POST_TURN_FEEDBACK: {claim_id}",
                            )
                        )

            optional_mediators = sum(
                1
                for path_node in ordered
                if isinstance(path_node, dict)
                and path_node.get("path_node_role") == "CAUSAL_MEDIATOR"
                and nodes.get(path_node.get("node_id"), {}).get("importance") == "OPTIONAL"
            )
            if optional_mediators > 4:
                self.warnings.append(CompileIssue("W_LONG_OPTIONAL_PATH", path, "more than four optional mediators"))
        self._validate_alternative_groups(paths)
        return paths

    def _validate_graph_contract(
        self,
        nodes: dict[str, dict[str, Any]],
        paths: dict[str, dict[str, Any]],
    ) -> None:
        if self.graph.get("schema_version") != "causal-factor-graph-v1.1":
            self.issues.append(CompileIssue("E_GRAPH_SCHEMA_VERSION", "graph.schema_version", "unsupported graph schema version"))
        if self.graph.get("source_policy_version") != self.source_claims.get("source_policy_version"):
            self.issues.append(CompileIssue("E_SOURCE_POLICY_MISMATCH", "graph.source_policy_version", "graph and source claims policy versions differ"))
        complexity = self.graph.get("complexity_profile")
        if isinstance(complexity, dict):
            required_counts = [
                len(path.get("required_semantic_segments", []))
                for path in paths.values()
                if path.get("importance") == "REQUIRED" and path.get("applicability") == "APPLICABLE"
            ]
            expected = max(required_counts, default=0)
            if complexity.get("required_segment_count") != expected:
                self.issues.append(
                    CompileIssue("E_COMPLEXITY_SEGMENT_COUNT", "graph.complexity_profile.required_segment_count", f"expected {expected}")
                )
            if not self.graph.get("fixture_only"):
                if complexity.get("author_review_status") != "VERIFIED":
                    self.issues.append(
                        CompileIssue("E_AUTHOR_REVIEW_REQUIRED", "graph.complexity_profile.author_review_status", "non-fixture graph must be VERIFIED")
                    )
                else:
                    self._validate_author_reviews()
        if not self.graph.get("fixture_only"):
            fixture_claims = [
                item.get("claim_id")
                for item in self.source_claims.get("claims", [])
                if item.get("source_type") == "FIXTURE"
            ]
            if fixture_claims:
                self.issues.append(
                    CompileIssue("E_FIXTURE_SOURCE_IN_PRODUCTION", "source_claims.claims", f"replace fixture claims: {fixture_claims}")
                )
        config = self.graph.get("m6_config", {})
        if config:
            weights = config.get("component_weights", {})
            values = [
                weights.get("target_exposure_reasoning"),
                weights.get("causal_transmission_reasoning"),
            ]
            if any(not isinstance(value, (int, float)) or value < 0 for value in values) or sum(value for value in values if isinstance(value, (int, float))) <= 0:
                self.issues.append(CompileIssue("E_M6_COMPONENT_WEIGHTS", "graph.m6_config.component_weights", "two non-negative weights with positive sum required"))
            stock_entities = {
                entity_id
                for node in nodes.values()
                if node.get("scope") == "STOCK"
                for entity_id in node.get("entity_ids", [])
            }
            unknown = set(config.get("required_entity_ids", [])) - stock_entities
            if unknown:
                self.issues.append(CompileIssue("E_M6_UNKNOWN_REQUIRED_ENTITY", "graph.m6_config.required_entity_ids", f"unknown stock entities: {sorted(unknown)}"))

    def _validate_author_reviews(self) -> None:
        reviews = self.graph.get("author_reviews")
        if not isinstance(reviews, list):
            self.issues.append(CompileIssue("E_AUTHOR_REVIEW_EVIDENCE", "graph.author_reviews", "review records are required"))
            return
        approved = [
            item
            for item in reviews
            if isinstance(item, dict)
            and item.get("decision") == "APPROVE"
            and item.get("graph_version") == self.graph.get("graph_version")
        ]
        pass_ids = {item.get("review_pass_id") for item in approved if item.get("review_pass_id")}
        reviewer_ids = {item.get("reviewer_id") for item in approved if item.get("reviewer_id")}
        times: list[datetime] = []
        for index, review in enumerate(approved):
            parsed = _parse_datetime(
                review.get("reviewed_at"),
                field_path=f"graph.author_reviews[{index}].reviewed_at",
                issues=self.issues,
            )
            if parsed is not None:
                times.append(parsed)
        independent_recheck = len(times) >= 2 and (max(times) - min(times)).total_seconds() >= 86400
        if len(pass_ids) < 2 or not (len(reviewer_ids) >= 2 or independent_recheck):
            self.issues.append(
                CompileIssue(
                    "E_AUTHOR_REVIEW_EVIDENCE",
                    "graph.author_reviews",
                    "two approval passes by distinct reviewers or at least 24 hours apart are required",
                )
            )

    def _validate_alternative_groups(self, paths: dict[str, dict[str, Any]]) -> None:
        groups: dict[str, list[dict[str, Any]]] = {}
        for path in paths.values():
            group_id = path.get("alternative_group_id")
            if group_id:
                groups.setdefault(group_id, []).append(path)
        for group_id, members in groups.items():
            target_sets = {tuple(sorted(path.get("target_entity_ids", []))) for path in members}
            segment_counts = {len(path.get("required_semantic_segments", [])) for path in members}
            if len(target_sets) > 1:
                self.issues.append(CompileIssue("E_ALTERNATIVE_TARGET_MISMATCH", f"graph.paths[{group_id}]", "alternative paths must share targets"))
            if len(segment_counts) > 1:
                self.issues.append(CompileIssue("E_ALTERNATIVE_COMPLEXITY_MISMATCH", f"graph.paths[{group_id}]", "alternative paths must have equal required segment counts"))

    def _validate_claim_refs(
        self,
        owner_path: str,
        claim_refs: Any,
        claims: dict[str, dict[str, Any]],
    ) -> None:
        if not isinstance(claim_refs, list):
            self.issues.append(CompileIssue("E_CLAIM_REFS", f"{owner_path}.source_claim_refs", "must be an array"))
            return
        for claim_id in claim_refs:
            if claim_id not in claims:
                self.issues.append(CompileIssue("E_UNKNOWN_CLAIM", f"{owner_path}.source_claim_refs", f"unknown claim: {claim_id}"))

    @staticmethod
    def _has_mandatory_claim(claim_refs: Any, claims: dict[str, dict[str, Any]]) -> bool:
        return isinstance(claim_refs, list) and any(
            claims.get(claim_id, {}).get("scoring_eligibility") == "MANDATORY_ELIGIBLE"
            for claim_id in claim_refs
        )


def compile_files(
    *,
    factor_catalog_path: str | Path,
    source_claims_path: str | Path,
    graph_path: str | Path,
) -> dict[str, Any]:
    compiler = GraphCompiler(
        factor_catalog=load_json(factor_catalog_path),
        source_claims=load_json(source_claims_path),
        graph=load_json(graph_path),
    )
    return compiler.compile()
