from __future__ import annotations

from typing import Any

from .bundle import EvaluatorBundle
from .canonical import sha256_json
from .contracts import DecisionInput
from .extractor import HybridEvidenceExtractor
from .feedback import FeedbackPlanner, KoreanTemplateRenderer
from .matcher import GraphMatcher
from .novel import collect_novel_path_candidates
from .providers import CandidateProvider
from .relations import HybridRelationExtractor
from .scoring import M6Scorer
from .temporal import TemporalPolicy
from .validator import validate_decision

ENGINE_VERSION = "causal-evaluator-v0.2.0"


class CausalEvaluator:
    def __init__(self, bundle: EvaluatorBundle) -> None:
        bundle.verify()
        self.bundle = bundle
        self.graph = bundle.graph
        self.extractor = HybridEvidenceExtractor(bundle.factor_catalog, self.graph)
        self.relation_extractor = HybridRelationExtractor(self.graph)
        self.matcher = GraphMatcher(self.graph)
        self.scorer = M6Scorer(self.graph)
        self.temporal_policy = TemporalPolicy(bundle.source_claims, self.graph)
        self.feedback_planner = FeedbackPlanner(bundle.factor_catalog, bundle.source_claims, self.graph)
        self.renderer = KoreanTemplateRenderer()

    def evaluate(
        self,
        decision: DecisionInput | dict[str, Any],
        *,
        model_evidence_candidates: tuple[dict[str, Any], ...] = (),
        model_relation_candidates: tuple[dict[str, Any], ...] = (),
        candidate_provider: CandidateProvider | None = None,
    ) -> dict[str, Any]:
        if isinstance(decision, dict):
            decision = DecisionInput.from_dict(decision)
        validate_decision(decision, self.graph)
        self.temporal_policy.validate_decision_visibility(decision)
        input_snapshot = decision.to_snapshot_dict()
        input_snapshot_hash = sha256_json(input_snapshot)
        parser_context = self.temporal_policy.parser_context(decision, self.bundle.factor_catalog)
        if candidate_provider is not None:
            model_evidence_candidates = (
                *model_evidence_candidates,
                *candidate_provider.evidence_candidates(parser_context),
            )
        evidence = self.extractor.extract(
            decision.answers,
            model_candidates=model_evidence_candidates,
        )
        if candidate_provider is not None:
            model_relation_candidates = (
                *model_relation_candidates,
                *candidate_provider.relation_candidates(parser_context, evidence),
            )
        relations = self.relation_extractor.extract(
            decision.answers,
            evidence,
            model_candidates=model_relation_candidates,
        )
        matches = self.matcher.match(evidence, relations)
        novel_path_candidates = collect_novel_path_candidates(evidence, relations, self.graph)
        m6 = self.scorer.score(decision, evidence, relations, matches)
        feedback_plan = self.feedback_planner.plan(matches)
        feedback = self.renderer.render(feedback_plan)
        record_identity = {
            "session_id": decision.session_id,
            "turn_no": decision.turn_no,
            "evaluator_bundle_id": self.bundle.bundle_id,
            "input_snapshot_hash": input_snapshot_hash,
        }
        return {
            "engine_version": ENGINE_VERSION,
            "evaluation_record_id": "eval-" + sha256_json(record_identity).removeprefix("sha256:")[:24],
            **record_identity,
            "scenario_id": decision.scenario_id,
            "scenario_version": decision.scenario_version,
            "evaluation_mode": "SHADOW",
            "legacy_score_effect": 0,
            "evidence": [item.to_dict() for item in evidence],
            "relation_evidence": [item.to_dict() for item in relations],
            "novel_path_candidates": novel_path_candidates,
            "m6": m6,
            "feedback_plan": feedback_plan,
            "feedback": feedback,
            "audit": {
                "factor_catalog_version": self.bundle.manifest["members"]["factor_catalog_version"],
                "graph_version": self.bundle.manifest["members"]["graph_version"],
                "graph_compile_hash": self.bundle.manifest["members"]["graph_compile_hash"],
                "source_policy_version": self.bundle.manifest["members"]["source_policy_version"],
                "source_snapshot": self.temporal_policy.source_snapshot(decision),
                "parser_context_hash": sha256_json(
                    parser_context
                ),
                "candidate_provider_version": getattr(candidate_provider, "provider_version", None),
                "future_information_used": False,
            },
        }
