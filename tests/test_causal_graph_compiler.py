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

from causal_engine import GraphCompileError, GraphCompiler  # noqa: E402


class GraphCompilerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        fixture_dir = ROOT / "examples" / "semiconductor_turn2"
        cls.catalog = cls._load(fixture_dir / "factor_catalog.json")
        cls.claims = cls._load(fixture_dir / "source_claims.json")
        cls.graph = cls._load(fixture_dir / "graph.json")

    @staticmethod
    def _load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def compile(self, *, catalog=None, claims=None, graph=None):
        return GraphCompiler(
            factor_catalog=copy.deepcopy(catalog or self.catalog),
            source_claims=copy.deepcopy(claims or self.claims),
            graph=copy.deepcopy(graph or self.graph),
        ).compile()

    def assert_issue(self, expected_code: str, *, catalog=None, claims=None, graph=None) -> None:
        with self.assertRaises(GraphCompileError) as context:
            self.compile(catalog=catalog, claims=claims, graph=graph)
        actual_codes = {issue.code for issue in context.exception.issues}
        self.assertIn(expected_code, actual_codes, context.exception)

    def test_valid_fixture_compiles_with_stable_hash(self) -> None:
        first = self.compile()
        second = self.compile()

        self.assertEqual(first["graph_compile_hash"], second["graph_compile_hash"])
        self.assertEqual(first["warning_count"], 0)
        self.assertTrue(first["graph_compile_hash"].startswith("sha256:"))

    def test_future_mandatory_claim_is_rejected(self) -> None:
        claims = copy.deepcopy(self.claims)
        claims["claims"][0]["available_at"] = "2024-02-23T09:00:00+09:00"

        self.assert_issue("E_TEMPORAL_LEAKAGE", claims=claims)

    def test_disconnected_path_is_rejected(self) -> None:
        graph = copy.deepcopy(self.graph)
        graph["paths"][0]["edge_ids"].remove("E-EXPOSURE-TO-EARNINGS")

        self.assert_issue("E_PATH_DISCONNECTED", graph=graph)

    def test_role_not_allowed_for_factor_is_rejected(self) -> None:
        graph = copy.deepcopy(self.graph)
        graph["paths"][0]["path_nodes"][1]["path_node_role"] = "TARGET_OUTCOME"

        self.assert_issue("E_ROLE_NOT_ALLOWED", graph=graph)

    def test_more_than_four_required_segments_is_rejected(self) -> None:
        graph = copy.deepcopy(self.graph)
        graph["paths"][0]["required_semantic_segments"].append(
            {"segment_id": "EXTRA", "one_of_node_ids": ["N-HBM-DEMAND"]}
        )

        self.assert_issue("E_TOO_MANY_SEGMENTS", graph=graph)

    def test_post_turn_path_cannot_use_retrospective_claim(self) -> None:
        claims = copy.deepcopy(self.claims)
        claims["claims"][1]["knowledge_role"] = "RETROSPECTIVE_ANALYSIS"

        self.assert_issue("E_POST_TURN_FUTURE_INFO", claims=claims)

    def test_hidden_mandatory_claim_requires_approved_prior_knowledge(self) -> None:
        claims = copy.deepcopy(self.claims)
        claims["claims"][0]["visibility_status"] = "NOT_VISIBLE_TO_USER"

        self.assert_issue("E_MANDATORY_VISIBILITY", claims=claims)

    def test_all_schema_documents_are_valid_json(self) -> None:
        schema_paths = sorted((ROOT / "schemas").glob("*.schema.json"))
        self.assertEqual(len(schema_paths), 6)
        for schema_path in schema_paths:
            schema = self._load(schema_path)
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertIn("$id", schema)


if __name__ == "__main__":
    unittest.main()


