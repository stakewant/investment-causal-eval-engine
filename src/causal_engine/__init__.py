"""Temporal causal-path evaluation primitives.

This package is intentionally isolated from the legacy M1-M5 research code.
Nothing in here changes the current user-visible score.
"""

from .compiler import COMPILER_VERSION, GraphCompiler, compile_files
from .errors import CompileIssue, GraphCompileError

__all__ = [
    "COMPILER_VERSION",
    "CompileIssue",
    "GraphCompileError",
    "GraphCompiler",
    "compile_files",
]


