from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from causal_engine.dataset import read_jsonl, training_rows, validate_annotations  # noqa: E402
from causal_engine.learning import HashedSoftmaxClassifier, RubricCalibrator  # noqa: E402
from causal_engine.experiment import run_experiment  # noqa: E402
from causal_engine.metrics import (  # noqa: E402
    bootstrap_confidence_interval,
    group_bootstrap_confidence_interval,
    inter_rater_report,
    macro_f1,
    quadratic_weighted_kappa,
    span_f1,
)


class ResearchToolingTest(unittest.TestCase):
    def test_seed_annotations_are_grounded_and_split_safe(self) -> None:
        records = read_jsonl(ROOT / "examples" / "annotations_seed.jsonl")
        report = validate_annotations(records)
        self.assertTrue(report["valid"], report)
        self.assertEqual(report["split_leakage_group_count"], 0)
        self.assertGreaterEqual(len(training_rows(records)), 10)

    def test_split_leakage_is_detected_by_user_and_scenario(self) -> None:
        record = {
            "schema_version": "causal-annotation-v1",
            "sample_id": "A",
            "split": "train",
            "group": {"user_id": "U", "scenario_id": "S"},
            "text": "요인",
            "annotations": {"evidence": [], "relations": []},
        }
        second = {**record, "sample_id": "B", "split": "test"}
        report = validate_annotations([record, second])
        self.assertFalse(report["valid"])
        self.assertEqual(report["split_leakage_group_count"], 1)

    def test_metrics_cover_spans_ordinal_scores_and_rater_agreement(self) -> None:
        self.assertEqual(quadratic_weighted_kappa([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]), 1.0)
        self.assertEqual(macro_f1(["A", "B"], ["A", "B"]), 1.0)
        self.assertEqual(span_f1([(0, 2, "A")], [(0, 2, "A")])["f1"], 1.0)
        report = inter_rater_report([[1, 1], [2, 2], [3, 3], [4, 4]])
        self.assertAlmostEqual(report["icc_absolute_single"], 1.0)
        interval = bootstrap_confidence_interval([1, 2, 3], [1, 2, 3], lambda a, b: quadratic_weighted_kappa(a, b), samples=20)
        self.assertEqual(interval["estimate"], 1.0)
        grouped = group_bootstrap_confidence_interval(
            [1, 2, 3, 4], [1, 2, 3, 4], ["A", "A", "B", "B"],
            lambda a, b: quadratic_weighted_kappa(a, b), samples=20,
        )
        self.assertEqual(grouped["estimate"], 1.0)

    def test_learned_candidate_baseline_round_trips(self) -> None:
        texts = ["수요 증가", "수요 확대", "실적 악화", "매출 감소"] * 3
        labels = ["POSITIVE", "POSITIVE", "NEGATIVE", "NEGATIVE"] * 3
        model = HashedSoftmaxClassifier(dimensions=128).fit(texts, labels, epochs=35)
        self.assertEqual(model.predict("수요 증가")[0], "POSITIVE")
        self.assertEqual(model.predict("실적 악화")[0], "NEGATIVE")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            model.save(path)
            restored = HashedSoftmaxClassifier.load(path)
            self.assertEqual(restored.predict("매출 감소")[0], "NEGATIVE")

    def test_rubric_calibrator_output_stays_on_m6_scale(self) -> None:
        model = RubricCalibrator(2, hidden_size=3)
        model.fit([[1, 1], [2, 2], [4, 4], [5, 5]], [1, 2, 4, 5], epochs=20)
        self.assertTrue(1.0 <= model.predict([3, 3]) <= 5.0)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "calibrator.json"
            model.save(path)
            restored = RubricCalibrator.load(path)
            self.assertAlmostEqual(model.predict([3, 3]), restored.predict([3, 3]))

    def test_two_reviewers_can_annotate_same_sample(self) -> None:
        base = {
            "schema_version": "causal-annotation-v1",
            "sample_id": "SAME",
            "split": "test",
            "group": {"user_id": "U", "scenario_id": "S"},
            "text": "요인",
            "annotations": {"evidence": [], "relations": []},
        }
        report = validate_annotations([
            {**base, "reviewer_id": "R1"},
            {**base, "reviewer_id": "R2"},
        ])
        self.assertTrue(report["valid"], report)

    def test_regression_experiment_manifest_passes(self) -> None:
        report = run_experiment(ROOT / "examples" / "semiconductor_turn2" / "experiment.json")
        self.assertTrue(report["passed"], report)
        self.assertEqual(report["pass_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
