from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from causal_engine.bundle import EvaluatorBundle, build_bundle  # noqa: E402
from causal_engine.errors import BundleError  # noqa: E402
from causal_engine.evaluator import CausalEvaluator  # noqa: E402
from causal_engine.canonical import sha256_json  # noqa: E402
from causal_engine.contracts import DecisionInput  # noqa: E402
from causal_engine.providers import CachedCandidateProvider  # noqa: E402


class EvaluatorPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture = ROOT / "examples" / "semiconductor_turn2"
        cls.catalog = cls.load(fixture / "factor_catalog.json")
        cls.claims = cls.load(fixture / "source_claims.json")
        cls.graph = cls.load(fixture / "graph.json")
        cls.decisions = {
            name: cls.load(fixture / f"decision_{name}.json")
            for name in ("complete", "partial", "list_only")
        }
        cls.bundle = build_bundle(
            factor_catalog=cls.catalog,
            source_claims=cls.claims,
            graph=cls.graph,
        )
        cls.evaluator = CausalEvaluator(cls.bundle)

    @staticmethod
    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def test_complete_answer_scores_complete_path(self) -> None:
        result = self.evaluator.evaluate(self.decisions["complete"])
        self.assertEqual(result["m6"]["status"], "SCORED")
        self.assertEqual(result["m6"]["path_matches"][0]["status"], "COMPLETE")
        self.assertEqual(result["m6"]["final_m6"], 5.0)
        self.assertEqual(result["feedback_plan"]["validation_status"], "ACCEPTED")
        self.assertFalse(result["audit"]["future_information_used"])

    def test_partial_answer_keeps_partial_credit(self) -> None:
        result = self.evaluator.evaluate(self.decisions["partial"])
        self.assertEqual(result["m6"]["path_matches"][0]["status"], "PARTIAL")
        self.assertGreater(result["m6"]["final_m6"], 1.0)
        self.assertLess(result["m6"]["final_m6"], 4.0)

    def test_factor_list_without_relations_is_disconnected_and_capped(self) -> None:
        result = self.evaluator.evaluate(self.decisions["list_only"])
        self.assertEqual(result["m6"]["path_matches"][0]["status"], "DISCONNECTED")
        self.assertLessEqual(result["m6"]["final_m6"], 3.0)
        caps = {item["policy_id"] for item in result["m6"]["caps_applied"]}
        self.assertIn("M6-CAP-LIST-ONLY-01", caps)

    def test_unprompted_industry_only_answer_is_not_assessed(self) -> None:
        decision = copy.deepcopy(self.decisions["partial"])
        decision["session_id"] = "not-assessed"
        decision["answers"][0]["target_entity_ids"] = []
        decision["answers"][0]["requires_explanation"] = False
        decision["answers"][0]["text"] = "AI 투자 확대 때문에 HBM 수요 증가가 이어진다."
        result = self.evaluator.evaluate(decision)
        self.assertEqual(result["m6"]["status"], "NOT_ASSESSED")
        self.assertNotIn("final_m6", result["m6"])

    def test_same_input_and_bundle_are_byte_level_deterministic_as_objects(self) -> None:
        first = self.evaluator.evaluate(self.decisions["complete"])
        second = self.evaluator.evaluate(self.decisions["complete"])
        self.assertEqual(first, second)
        self.assertEqual(first["evaluation_record_id"], second["evaluation_record_id"])

    def test_bundle_tampering_is_rejected(self) -> None:
        value = self.bundle.to_dict()
        value["resources"]["factor_catalog"]["catalog_version"] = "tampered"
        with self.assertRaises(BundleError):
            EvaluatorBundle.from_dict(value)

    def test_cached_external_candidates_are_bound_to_parser_context(self) -> None:
        decision = self.decisions["complete"]
        parsed = self.evaluator.temporal_policy.parser_context(
            DecisionInput.from_dict(decision),
            self.catalog,
        )
        provider = CachedCandidateProvider(
            {
                "format_version": "cached-candidates-v1",
                "provider_version": "test-neural-v1",
                "parser_context_hash": sha256_json(parsed),
                "evidence_candidates": [],
                "relation_candidates": [],
            }
        )
        result = self.evaluator.evaluate(decision, candidate_provider=provider)
        self.assertEqual(result["audit"]["candidate_provider_version"], "test-neural-v1")
        provider.value["parser_context_hash"] = "sha256:" + "0" * 64
        with self.assertRaises(ValueError):
            self.evaluator.evaluate(decision, candidate_provider=provider)

    def test_noncanonical_model_relation_enters_review_queue_without_score_effect(self) -> None:
        result = self.evaluator.evaluate(
            self.decisions["complete"],
            model_relation_candidates=(
                {
                    "source_evidence_id": "EV-0001",
                    "target_evidence_id": "EV-0004",
                    "relation": "CAUSES",
                    "sign": "POSITIVE",
                    "explicitness": "EXPLICIT",
                    "connector_span": "장기적으로",
                    "model_confidence": 0.92,
                },
            ),
        )
        self.assertEqual(len(result["novel_path_candidates"]), 1)
        self.assertEqual(result["novel_path_candidates"][0]["status"], "REVIEW_REQUIRED")
        self.assertEqual(result["novel_path_candidates"][0]["automatic_score_effect"], 0)
        self.assertEqual(result["m6"]["final_m6"], 5.0)

    def test_correct_industry_but_wrong_stock_exposure_is_capped(self) -> None:
        catalog = copy.deepcopy(self.catalog)
        catalog["entities"].append(
            {"entity_id": "005930", "label": "삼성전자", "aliases": ["삼성전자"], "scope": "STOCK"}
        )
        evaluator = CausalEvaluator(
            build_bundle(factor_catalog=catalog, source_claims=self.claims, graph=self.graph)
        )
        decision = copy.deepcopy(self.decisions["complete"])
        decision["session_id"] = "wrong-target"
        decision["answers"][0]["text"] = (
            "AI 투자 확대 때문에 HBM 수요 증가가 이어지고, 삼성전자의 HBM 제품 비중이 "
            "해당 수요에 노출되어 실적 개선 기대가 커진다고 봤다."
        )
        result = evaluator.evaluate(decision)
        self.assertEqual(result["m6"]["industry_to_stock_link"], "INVALID")
        self.assertLessEqual(result["m6"]["final_m6"], 2.5)
        self.assertIn(
            "M6-CAP-TARGET-FALSE-01",
            {item["policy_id"] for item in result["m6"]["caps_applied"]},
        )


if __name__ == "__main__":
    unittest.main()
