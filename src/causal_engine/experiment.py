from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .bundle import build_bundle
from .compiler import load_json
from .evaluator import CausalEvaluator

EXPERIMENT_FORMAT_VERSION = "causal-experiment-v1"


def run_experiment(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path)
    manifest = load_json(path)
    if manifest.get("format_version") != EXPERIMENT_FORMAT_VERSION:
        raise ValueError("unsupported experiment manifest format")
    base = path.parent
    bundle_config = manifest["bundle"]
    bundle = build_bundle(
        factor_catalog=load_json(base / bundle_config["catalog"]),
        source_claims=load_json(base / bundle_config["claims"]),
        graph=load_json(base / bundle_config["graph"]),
    )
    evaluator = CausalEvaluator(bundle)
    cases = []
    for case in manifest.get("cases", []):
        decision = load_json(base / case["input"])
        result = evaluator.evaluate(decision)
        expected = case.get("expected", {})
        assertions = {
            "m6_status": result["m6"]["status"] == expected.get("m6_status", result["m6"]["status"]),
            "path_status": result["m6"]["path_matches"][0]["status"]
            == expected.get("path_status", result["m6"]["path_matches"][0]["status"]),
        }
        score = result["m6"].get("final_m6")
        if "minimum_m6" in expected:
            assertions["minimum_m6"] = score is not None and score >= float(expected["minimum_m6"])
        if "maximum_m6" in expected:
            assertions["maximum_m6"] = score is not None and score <= float(expected["maximum_m6"])
        cases.append(
            {
                "case_id": case["case_id"],
                "passed": all(assertions.values()),
                "assertions": assertions,
                "actual": {
                    "m6_status": result["m6"]["status"],
                    "path_status": result["m6"]["path_matches"][0]["status"],
                    "final_m6": score,
                    "evaluation_record_id": result["evaluation_record_id"],
                },
            }
        )
    return {
        "format_version": EXPERIMENT_FORMAT_VERSION,
        "experiment_id": manifest["experiment_id"],
        "evaluator_bundle_id": bundle.bundle_id,
        "case_count": len(cases),
        "passed_count": sum(item["passed"] for item in cases),
        "pass_rate": sum(item["passed"] for item in cases) / len(cases) if cases else 0.0,
        "passed": all(item["passed"] for item in cases),
        "cases": cases,
    }
