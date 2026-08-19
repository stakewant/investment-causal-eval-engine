from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .bundle import EvaluatorBundle, build_bundle_from_files
from .dataset import read_jsonl, training_rows, validate_annotations
from .evaluator import CausalEvaluator
from .experiment import run_experiment
from .learning import HashedSoftmaxClassifier, RubricCalibrator
from .metrics import (
    bootstrap_confidence_interval,
    classification_report,
    expected_calibration_error,
    group_bootstrap_confidence_interval,
    inter_rater_report,
    mean_absolute_error,
    quadratic_weighted_kappa,
    root_mean_squared_error,
)
from .providers import CachedCandidateProvider


def _write(value: object, path: str | None = None) -> None:
    rendered = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Investment causal evaluation research engine")
    commands = parser.add_subparsers(dest="command", required=True)
    bundle = commands.add_parser("build-bundle")
    bundle.add_argument("--catalog", required=True)
    bundle.add_argument("--claims", required=True)
    bundle.add_argument("--graph", required=True)
    bundle.add_argument("--output", required=True)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--bundle", required=True)
    evaluate.add_argument("--input", required=True)
    evaluate.add_argument("--output")
    evaluate.add_argument("--candidates", help="optional cached neural/embedding/LLM candidate JSON")
    annotations = commands.add_parser("validate-annotations")
    annotations.add_argument("--input", required=True)
    annotations.add_argument("--output")
    export = commands.add_parser("export-training")
    export.add_argument("--input", required=True)
    export.add_argument("--output", required=True)
    train = commands.add_parser("train-classifier")
    train.add_argument("--input", required=True)
    train.add_argument("--task", required=True)
    train.add_argument("--model", required=True)
    train.add_argument("--epochs", type=int, default=25)
    predict = commands.add_parser("predict")
    predict.add_argument("--model", required=True)
    predict.add_argument("--text", required=True)
    metrics = commands.add_parser("metrics")
    metrics.add_argument("--input", required=True, help="JSONL with gold and predicted fields")
    metrics.add_argument("--type", choices=("classification", "ordinal", "agreement"), required=True)
    metrics.add_argument("--output")
    experiment = commands.add_parser("run-experiment")
    experiment.add_argument("--manifest", required=True)
    experiment.add_argument("--output")
    calibrator = commands.add_parser("train-calibrator")
    calibrator.add_argument("--input", required=True, help="JSONL with features array and gold score")
    calibrator.add_argument("--model", required=True)
    calibrator.add_argument("--epochs", type=int, default=500)
    calibrate = commands.add_parser("calibrate")
    calibrate.add_argument("--model", required=True)
    calibrate.add_argument("--features", required=True, help="comma-separated numeric features")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "build-bundle":
            bundle = build_bundle_from_files(
                factor_catalog_path=args.catalog,
                source_claims_path=args.claims,
                graph_path=args.graph,
                output_path=args.output,
            )
            _write(bundle.manifest)
        elif args.command == "evaluate":
            decision = json.loads(Path(args.input).read_text(encoding="utf-8-sig"))
            provider = CachedCandidateProvider.load(args.candidates) if args.candidates else None
            result = CausalEvaluator(EvaluatorBundle.load(args.bundle)).evaluate(
                decision, candidate_provider=provider
            )
            _write(result, args.output)
        elif args.command == "validate-annotations":
            _write(validate_annotations(read_jsonl(args.input)), args.output)
        elif args.command == "export-training":
            rows = training_rows(read_jsonl(args.input))
            target = Path(args.output)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
        elif args.command == "train-classifier":
            rows = [row for row in read_jsonl(args.input) if row.get("task") == args.task]
            model = HashedSoftmaxClassifier().fit(
                [str(row["text"]) for row in rows],
                [str(row["label"]) for row in rows],
                epochs=args.epochs,
            )
            model.save(args.model)
            _write({"task": args.task, "examples": len(rows), "labels": model.labels, "model": args.model})
        elif args.command == "predict":
            label, confidence = HashedSoftmaxClassifier.load(args.model).predict(args.text)
            _write({"label": label, "confidence": confidence})
        elif args.command == "metrics":
            rows = read_jsonl(args.input)
            if args.type == "classification":
                report = classification_report(
                    [str(row["gold"]) for row in rows], [str(row["predicted"]) for row in rows]
                )
                if all("confidence" in row for row in rows):
                    report["expected_calibration_error"] = expected_calibration_error(
                        [str(row["gold"]) == str(row["predicted"]) for row in rows],
                        [float(row["confidence"]) for row in rows],
                    )
            elif args.type == "ordinal":
                gold = [float(row["gold"]) for row in rows]
                predicted = [float(row["predicted"]) for row in rows]
                rounded_gold = [int(round(value)) for value in gold]
                rounded_predicted = [int(round(value)) for value in predicted]
                if all("group_id" in row for row in rows):
                    qwk_interval = group_bootstrap_confidence_interval(
                        rounded_gold,
                        rounded_predicted,
                        [str(row["group_id"]) for row in rows],
                        lambda a, b: quadratic_weighted_kappa(a, b),
                    )
                else:
                    qwk_interval = bootstrap_confidence_interval(
                        rounded_gold,
                        rounded_predicted,
                        lambda a, b: quadratic_weighted_kappa(a, b),
                    )
                report = {
                    "count": len(rows),
                    "mae": mean_absolute_error(gold, predicted),
                    "rmse": root_mean_squared_error(gold, predicted),
                    "qwk": quadratic_weighted_kappa(rounded_gold, rounded_predicted),
                    "qwk_bootstrap": qwk_interval,
                }
            else:
                report = inter_rater_report(
                    [[float(value) for value in row["ratings"]] for row in rows]
                )
            _write(report, args.output)
        elif args.command == "run-experiment":
            report = run_experiment(args.manifest)
            _write(report, args.output)
            if not report["passed"]:
                return 1
        elif args.command == "train-calibrator":
            rows = read_jsonl(args.input)
            if not rows:
                raise ValueError("calibrator training input is empty")
            features = [[float(value) for value in row["features"]] for row in rows]
            gold = [float(row["gold"]) for row in rows]
            model = RubricCalibrator(len(features[0])).fit(features, gold, epochs=args.epochs)
            model.save(args.model)
            _write({"examples": len(rows), "input_size": len(features[0]), "model": args.model})
        elif args.command == "calibrate":
            features = [float(value.strip()) for value in args.features.split(",")]
            _write({"calibrated_score": RubricCalibrator.load(args.model).predict(features)})
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
