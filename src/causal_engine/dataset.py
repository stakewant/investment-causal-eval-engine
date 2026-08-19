from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import ContractError

ANNOTATION_SCHEMA_VERSION = "causal-annotation-v1"


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    records = []
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ContractError(f"{path}:{line_no}: JSONL row must be an object")
            records.append(value)
    return records


def validate_annotations(records: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[str] = []
    annotation_keys: set[tuple[str, str]] = set()
    split_groups: dict[tuple[str, str], set[str]] = {}
    label_counts: dict[str, int] = {}
    for index, record in enumerate(records):
        prefix = f"records[{index}]"
        if record.get("schema_version") != ANNOTATION_SCHEMA_VERSION:
            issues.append(f"{prefix}.schema_version")
        sample_id = str(record.get("sample_id", ""))
        reviewer_id = str(record.get("reviewer_id", ""))
        annotation_key = (sample_id, reviewer_id)
        if not sample_id or not reviewer_id or annotation_key in annotation_keys:
            issues.append(f"{prefix}.sample_id")
        annotation_keys.add(annotation_key)
        text = str(record.get("text", ""))
        split = str(record.get("split", ""))
        if split not in {"train", "validation", "test"}:
            issues.append(f"{prefix}.split")
        group = record.get("group", {})
        key = (str(group.get("user_id", "")), str(group.get("scenario_id", "")))
        if not all(key):
            issues.append(f"{prefix}.group")
        split_groups.setdefault(key, set()).add(split)
        evidence_ids: set[str] = set()
        for ev_index, evidence in enumerate(record.get("annotations", {}).get("evidence", [])):
            start, end = evidence.get("character_start"), evidence.get("character_end")
            evidence_id = str(evidence.get("evidence_id", ""))
            if not evidence_id or evidence_id in evidence_ids:
                issues.append(f"{prefix}.annotations.evidence[{ev_index}].evidence_id")
            evidence_ids.add(evidence_id)
            if not isinstance(start, int) or not isinstance(end, int) or not (0 <= start < end <= len(text)):
                issues.append(f"{prefix}.annotations.evidence[{ev_index}].span")
            elif text[start:end] != evidence.get("evidence_span"):
                issues.append(f"{prefix}.annotations.evidence[{ev_index}].evidence_span")
            label = str(evidence.get("factor_id", ""))
            label_counts[label] = label_counts.get(label, 0) + 1
        for rel_index, relation in enumerate(record.get("annotations", {}).get("relations", [])):
            if relation.get("source_evidence_id") not in evidence_ids or relation.get("target_evidence_id") not in evidence_ids:
                issues.append(f"{prefix}.annotations.relations[{rel_index}].endpoints")
        score = record.get("annotations", {}).get("m6_score")
        if score is not None and not 1 <= float(score) <= 5:
            issues.append(f"{prefix}.annotations.m6_score")
    leakage_groups = [key for key, splits in split_groups.items() if len(splits - {""}) > 1]
    issues.extend(f"split_leakage:{user}:{scenario}" for user, scenario in leakage_groups)
    return {
        "record_count": len(records),
        "valid": not issues,
        "issues": issues,
        "split_leakage_group_count": len(leakage_groups),
        "factor_label_counts": label_counts,
    }


def training_rows(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for record in records:
        text = str(record.get("text", ""))
        annotations = record.get("annotations", {})
        evidence_by_id = {item["evidence_id"]: item for item in annotations.get("evidence", [])}
        for evidence in annotations.get("evidence", []):
            span = str(evidence.get("evidence_span", ""))
            rows.extend(
                [
                    {"task": "FACTOR", "text": span, "label": str(evidence.get("factor_id", ""))},
                    {"task": "SCOPE", "text": span, "label": str(evidence.get("scope", ""))},
                    {"task": "DIRECTION", "text": span, "label": str(evidence.get("direction", ""))},
                ]
            )
        for relation in annotations.get("relations", []):
            source = evidence_by_id.get(relation.get("source_evidence_id"), {})
            target = evidence_by_id.get(relation.get("target_evidence_id"), {})
            relation_text = " [CAUSE] ".join(
                [str(source.get("evidence_span", "")), str(target.get("evidence_span", ""))]
            )
            rows.append({"task": "RELATION", "text": relation_text, "label": str(relation.get("relation", ""))})
    return rows
