from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from .canonical import sha256_json
from .contracts import Evidence


class CandidateProvider(Protocol):
    """Two-stage extension point for neural, embedding or LLM candidates."""

    provider_version: str

    def evidence_candidates(self, parser_context: dict[str, Any]) -> tuple[dict[str, Any], ...]: ...

    def relation_candidates(
        self,
        parser_context: dict[str, Any],
        evidence: tuple[Evidence, ...],
    ) -> tuple[dict[str, Any], ...]: ...


class CachedCandidateProvider:
    """Replays externally generated candidates for deterministic offline experiments."""

    FORMAT = "cached-candidates-v1"

    def __init__(self, value: dict[str, Any]) -> None:
        if value.get("format_version") != self.FORMAT:
            raise ValueError("unsupported cached candidate format")
        self.value = value
        self.provider_version = str(value.get("provider_version", "cached-provider-unknown"))

    @classmethod
    def load(cls, path: str | Path) -> "CachedCandidateProvider":
        return cls(json.loads(Path(path).read_text(encoding="utf-8-sig")))

    def evidence_candidates(self, parser_context: dict[str, Any]) -> tuple[dict[str, Any], ...]:
        self._verify_context(parser_context)
        return tuple(self.value.get("evidence_candidates", []))

    def relation_candidates(
        self,
        parser_context: dict[str, Any],
        evidence: tuple[Evidence, ...],
    ) -> tuple[dict[str, Any], ...]:
        del evidence
        self._verify_context(parser_context)
        return tuple(self.value.get("relation_candidates", []))

    def _verify_context(self, parser_context: dict[str, Any]) -> None:
        expected = self.value.get("parser_context_hash")
        actual = sha256_json(parser_context)
        if expected and expected != actual:
            raise ValueError("cached candidates were generated from a different parser context")
