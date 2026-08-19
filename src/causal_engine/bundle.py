from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .canonical import sha256_json
from .compiler import GraphCompiler, load_json
from .errors import BundleError

BUNDLE_FORMAT_VERSION = "runtime-bundle-v1"
DEFAULT_MEMBERS = {
    "m6_policy_version": "m6-scoring-v1.1",
    "extractor_version": "hybrid-evidence-v0.2.0",
    "relation_extractor_version": "hybrid-relation-v0.2.0",
    "graph_ranker_version": "deterministic-segment-matcher-v0.2.0",
    "validator_version": "evidence-validator-v0.2.0",
    "llm_parser_version": None,
}


@dataclass(frozen=True)
class EvaluatorBundle:
    manifest: dict[str, Any]
    factor_catalog: dict[str, Any]
    source_claims: dict[str, Any]
    compiled_graph: dict[str, Any]

    @property
    def graph(self) -> dict[str, Any]:
        return self.compiled_graph["normalized_graph"]

    @property
    def bundle_id(self) -> str:
        return self.manifest["evaluator_bundle_id"]

    def to_dict(self) -> dict[str, Any]:
        return {
            "bundle_format_version": BUNDLE_FORMAT_VERSION,
            "manifest": self.manifest,
            "resources": {
                "factor_catalog": self.factor_catalog,
                "source_claims": self.source_claims,
                "compiled_graph": self.compiled_graph,
            },
        }

    @classmethod
    def from_dict(cls, value: dict[str, Any], *, verify: bool = True) -> "EvaluatorBundle":
        if value.get("bundle_format_version") != BUNDLE_FORMAT_VERSION:
            raise BundleError("unsupported or missing runtime bundle format")
        resources = value.get("resources")
        if not isinstance(resources, dict):
            raise BundleError("runtime bundle resources must be an object")
        bundle = cls(
            manifest=dict(value.get("manifest") or {}),
            factor_catalog=dict(resources.get("factor_catalog") or {}),
            source_claims=dict(resources.get("source_claims") or {}),
            compiled_graph=dict(resources.get("compiled_graph") or {}),
        )
        if verify:
            bundle.verify()
        return bundle

    @classmethod
    def load(cls, path: str | Path, *, verify: bool = True) -> "EvaluatorBundle":
        return cls.from_dict(load_json(path), verify=verify)

    def verify(self) -> None:
        resources_hash = sha256_json(
            {
                "factor_catalog": self.factor_catalog,
                "source_claims": self.source_claims,
                "compiled_graph": self.compiled_graph,
            }
        )
        if self.manifest.get("resources_hash") != resources_hash:
            raise BundleError("runtime bundle resource hash mismatch")
        manifest_payload = {
            key: value
            for key, value in self.manifest.items()
            if key not in {"bundle_hash", "evaluator_bundle_id"}
        }
        expected_hash = sha256_json(manifest_payload)
        if self.manifest.get("bundle_hash") != expected_hash:
            raise BundleError("evaluator bundle manifest hash mismatch")
        expected_id = "ceval-" + expected_hash.removeprefix("sha256:")[:20]
        if self.manifest.get("evaluator_bundle_id") != expected_id:
            raise BundleError("evaluator bundle id does not match manifest hash")
        if self.compiled_graph.get("graph_compile_hash") != self.manifest.get("members", {}).get(
            "graph_compile_hash"
        ):
            raise BundleError("compiled graph hash does not match bundle members")


def build_bundle(
    *,
    factor_catalog: dict[str, Any],
    source_claims: dict[str, Any],
    graph: dict[str, Any],
    member_overrides: dict[str, Any] | None = None,
) -> EvaluatorBundle:
    compiled = GraphCompiler(
        factor_catalog=factor_catalog,
        source_claims=source_claims,
        graph=graph,
    ).compile()
    members = {
        **DEFAULT_MEMBERS,
        "source_policy_version": compiled["source_policy_version"],
        "factor_catalog_version": factor_catalog["catalog_version"],
        "graph_schema_version": compiled["graph_schema_version"],
        "graph_version": compiled["graph_version"],
        "graph_compile_hash": compiled["graph_compile_hash"],
        **(member_overrides or {}),
    }
    resources_hash = sha256_json(
        {
            "factor_catalog": factor_catalog,
            "source_claims": source_claims,
            "compiled_graph": compiled,
        }
    )
    manifest_payload = {
        "members": members,
        "resources_hash": resources_hash,
    }
    bundle_hash = sha256_json(manifest_payload)
    manifest = {
        "evaluator_bundle_id": "ceval-" + bundle_hash.removeprefix("sha256:")[:20],
        "bundle_hash": bundle_hash,
        **manifest_payload,
    }
    return EvaluatorBundle(manifest, factor_catalog, source_claims, compiled)


def build_bundle_from_files(
    *,
    factor_catalog_path: str | Path,
    source_claims_path: str | Path,
    graph_path: str | Path,
    output_path: str | Path | None = None,
    member_overrides: dict[str, Any] | None = None,
) -> EvaluatorBundle:
    bundle = build_bundle(
        factor_catalog=load_json(factor_catalog_path),
        source_claims=load_json(source_claims_path),
        graph=load_json(graph_path),
        member_overrides=member_overrides,
    )
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(bundle.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return bundle
