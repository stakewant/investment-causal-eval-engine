from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from causal_engine.contracts import AnswerInput, DecisionInput  # noqa: E402
from causal_engine.errors import ContractError  # noqa: E402
from causal_engine.temporal import TemporalPolicy  # noqa: E402


class TemporalPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture = ROOT / "examples" / "semiconductor_turn2"
        cls.catalog = json.loads((fixture / "factor_catalog.json").read_text(encoding="utf-8-sig"))
        cls.claims = json.loads((fixture / "source_claims.json").read_text(encoding="utf-8-sig"))
        cls.graph = json.loads((fixture / "graph.json").read_text(encoding="utf-8-sig"))

    def decision(self, visible: tuple[str, ...]) -> DecisionInput:
        return DecisionInput(
            session_id="S",
            scenario_id="semiconductor-fixture",
            scenario_version=1,
            turn_no=2,
            answers=(AnswerInput("Q", "AI 투자 확대"),),
            visible_claim_ids=visible,
        )

    def test_parser_context_exposes_only_visible_as_of_claims_and_no_answer_graph(self) -> None:
        policy = TemporalPolicy(self.claims, self.graph)
        decision = self.decision(("CLM-FIX-AI-CAPEX",))
        context = policy.parser_context(decision, self.catalog)
        self.assertEqual([item["claim_id"] for item in context["visible_as_of_claims"]], ["CLM-FIX-AI-CAPEX"])
        self.assertNotIn("paths", context)
        self.assertNotIn("score", context)
        snapshot = policy.source_snapshot(decision)
        self.assertEqual(snapshot["mandatory_claim_ids"], ["CLM-FIX-AI-CAPEX"])
        self.assertTrue(snapshot["source_snapshot_hash"].startswith("sha256:"))

    def test_unknown_visible_claim_is_rejected(self) -> None:
        with self.assertRaises(ContractError):
            TemporalPolicy(self.claims, self.graph).validate_decision_visibility(self.decision(("UNKNOWN",)))

    def test_missing_mandatory_session_exposure_is_rejected(self) -> None:
        with self.assertRaises(ContractError) as context:
            TemporalPolicy(self.claims, self.graph).validate_decision_visibility(
                self.decision(("CLM-FIX-AI-CAPEX",))
            )
        self.assertIn("MANDATORY_CLAIM_NOT_SHOWN", str(context.exception))

    def test_future_visible_claim_is_rejected(self) -> None:
        claims = json.loads(json.dumps(self.claims))
        claims["claims"][0]["available_at"] = "2024-02-23T09:00:00+09:00"
        with self.assertRaises(ContractError):
            TemporalPolicy(claims, self.graph).validate_decision_visibility(
                self.decision(("CLM-FIX-AI-CAPEX",))
            )


if __name__ == "__main__":
    unittest.main()
