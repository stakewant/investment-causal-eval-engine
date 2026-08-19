"""Standalone temporal causal-path shadow evaluation engine.

The package is intentionally isolated from the legacy M1-M5 code. Every result
has ``legacy_score_effect=0`` until an independently approved promotion stage.
"""

from .bundle import EvaluatorBundle, build_bundle, build_bundle_from_files
from .compiler import COMPILER_VERSION, GraphCompiler, compile_files
from .contracts import DecisionInput, Evidence, PathMatch, RelationEvidence
from .errors import BundleError, CompileIssue, ContractError, EvaluationError, GraphCompileError
from .evaluator import CausalEvaluator
from .providers import CachedCandidateProvider, CandidateProvider

__all__ = [
    "COMPILER_VERSION",
    "BundleError",
    "CausalEvaluator",
    "CachedCandidateProvider",
    "CandidateProvider",
    "CompileIssue",
    "ContractError",
    "DecisionInput",
    "EvaluationError",
    "EvaluatorBundle",
    "Evidence",
    "GraphCompileError",
    "GraphCompiler",
    "PathMatch",
    "RelationEvidence",
    "build_bundle",
    "build_bundle_from_files",
    "compile_files",
]
