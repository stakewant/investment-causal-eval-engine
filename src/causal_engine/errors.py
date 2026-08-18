from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompileIssue:
    code: str
    path: str
    message: str

    def format(self) -> str:
        return f"[{self.code}] {self.path}: {self.message}"


class GraphCompileError(ValueError):
    def __init__(self, issues: list[CompileIssue]):
        self.issues = tuple(issues)
        message = "Causal graph compilation failed:\n" + "\n".join(
            f"- {issue.format()}" for issue in self.issues
        )
        super().__init__(message)


