from __future__ import annotations

import json
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from causal_engine.contracts import (  # noqa: E402
    AnswerInput,
    DecisionInput,
    Evidence,
    PathMatch,
    RelationEvidence,
)
from causal_engine.scoring import M6Scorer, round_half_up  # noqa: E402


class ScoringBoundaryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.graph = json.loads(
            (ROOT / "examples" / "semiconductor_turn2" / "graph.json").read_text(encoding="utf-8-sig")
        )

    def test_rounding_is_decimal_half_up(self) -> None:
        self.assertEqual(round_half_up(3.45), 3.5)
        self.assertEqual(round_half_up(3.44), 3.4)

    def test_m2_owned_direction_error_is_not_deducted_again(self) -> None:
        answer = AnswerInput(
            question_id="Q",
            text="AI 투자와 HBM 수요 및 SK하이닉스 HBM 제품 비중을 실적 기대까지 연결했다.",
            target_entity_ids=("000660",),
            requires_explanation=True,
        )
        base = dict(
            session_id="S",
            scenario_id="semiconductor-fixture",
            scenario_version=1,
            turn_no=2,
            answers=(answer,),
        )
        dependency = ({"error_code": "INDUSTRY_DIRECTION_REVERSED", "error_owner": "M2", "propagated_to": ["M6"]},)
        with_dependency = DecisionInput(**base, dependency_diagnostics=dependency)
        without_dependency = DecisionInput(**base)
        evidence = (
            Evidence("E1", "Q", 0, 0, 2, "AI", "AI_CAPEX_GROWTH", "MARKET", (), "NEGATIVE", "ASSERTED", False, ("RULE",), 1.0, "SCORE_ELIGIBLE", "test"),
            Evidence("E2", "Q", 0, 3, 6, "HBM", "HBM_DEMAND_GROWTH", "INDUSTRY", (), "NEGATIVE", "ASSERTED", False, ("RULE",), 1.0, "SCORE_ELIGIBLE", "test"),
        )
        relation = (
            RelationEvidence("R1", "E1", "E2", "CAUSES", "NEGATIVE", "때문", 0, "EXPLICIT", 1.0, ("E-AI-TO-HBM",), "SCORE_ELIGIBLE", "test"),
        )
        match = (
            PathMatch(
                "AI-TO-TARGET-EARNINGS", "APPLICABLE", "WRONG_DIRECTION",
                ("TRIGGER", "INDUSTRY_TRANSMISSION", "TARGET_EXPOSURE", "TARGET_OUTCOME"), (),
                ("N-AI-CAPEX", "N-HBM-DEMAND", "N-TARGET-HBM-EXPOSURE", "N-TARGET-EARNINGS"),
                ("E-AI-TO-HBM",), ("R1",), "VALID", ("DIRECTION_CONFLICT",), 1.0, ("000660",),
            ),
        )
        scorer = M6Scorer(self.graph)
        protected = scorer.score(with_dependency, evidence, relation, match)
        unprotected = scorer.score(without_dependency, evidence, relation, match)
        self.assertGreater(
            protected["asset_results"][0]["components"]["causal_transmission_reasoning"]["score"],
            unprotected["asset_results"][0]["components"]["causal_transmission_reasoning"]["score"],
        )
        self.assertTrue(protected["asset_results"][0]["dependency_failed_m2"])

    def test_required_direct_and_indirect_paths_are_both_counted(self) -> None:
        graph = copy.deepcopy(self.graph)
        direct = copy.deepcopy(graph["paths"][0])
        direct["path_id"] = "DIRECT-ALT-INDEPENDENT"
        direct["path_class"] = "DIRECT"
        graph["paths"].append(direct)
        scorer = M6Scorer(graph)
        decision = DecisionInput(
            session_id="S",
            scenario_id="semiconductor-fixture",
            scenario_version=1,
            turn_no=2,
            answers=(
                AnswerInput(
                    "Q",
                    "AI 투자 확대가 HBM 수요와 SK하이닉스 HBM 매출 노출을 거쳐 실적에 연결된다.",
                    target_entity_ids=("000660",),
                    requires_explanation=True,
                ),
            ),
        )
        evidence = (
            Evidence("E1", "Q", 0, 0, 2, "AI", "AI_CAPEX_GROWTH", "MARKET", (), "POSITIVE", "ASSERTED", False, ("RULE",), 1.0, "SCORE_ELIGIBLE", "test"),
            Evidence("E2", "Q", 0, 3, 6, "HBM", "TARGET_HBM_PRODUCT_EXPOSURE", "STOCK", ("000660",), "POSITIVE", "ASSERTED", False, ("RULE",), 1.0, "SCORE_ELIGIBLE", "test"),
        )
        relations = (
            RelationEvidence("R1", "E1", "E2", "CAUSES", "POSITIVE", "연결", 0, "EXPLICIT", 1.0, ("E-HBM-TO-TARGET-EXPOSURE",), "SCORE_ELIGIBLE", "test"),
        )
        complete = PathMatch(
            "DIRECT-ALT-INDEPENDENT", "APPLICABLE", "COMPLETE",
            ("TRIGGER", "INDUSTRY_TRANSMISSION", "TARGET_EXPOSURE", "TARGET_OUTCOME"), (),
            ("N-AI-CAPEX", "N-HBM-DEMAND", "N-TARGET-HBM-EXPOSURE", "N-TARGET-EARNINGS"),
            ("E-AI-TO-HBM", "E-HBM-TO-TARGET-EXPOSURE", "E-EXPOSURE-TO-EARNINGS"),
            ("R1",), "VALID", (), 1.0, ("000660",),
        )
        missing = PathMatch(
            "AI-TO-TARGET-EARNINGS", "APPLICABLE", "MISSING", (),
            ("TRIGGER", "INDUSTRY_TRANSMISSION", "TARGET_EXPOSURE", "TARGET_OUTCOME"),
            (), (), (), "MISSING", (), 0.0, ("000660",),
        )
        result = scorer.score(decision, evidence, relations, (complete, missing))
        self.assertEqual(
            set(result["asset_results"][0]["selected_path_ids"]),
            {"DIRECT-ALT-INDEPENDENT", "AI-TO-TARGET-EARNINGS"},
        )
        self.assertLessEqual(result["final_m6"], 3.0)


if __name__ == "__main__":
    unittest.main()
