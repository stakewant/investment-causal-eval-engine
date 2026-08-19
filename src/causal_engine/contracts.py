from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ValidationStatus = Literal[
    "SCORE_ELIGIBLE", "FEEDBACK_ONLY", "REVIEW_REQUIRED", "REJECTED"
]


@dataclass(frozen=True)
class AnswerInput:
    question_id: str
    text: str = ""
    selected: tuple[str, ...] = ()
    target_entity_ids: tuple[str, ...] = ()
    requires_explanation: bool = False

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "AnswerInput":
        return cls(
            question_id=str(value.get("question_id", "")),
            text=str(value.get("text", "")),
            selected=tuple(str(item) for item in value.get("selected", []) or []),
            target_entity_ids=tuple(
                str(item) for item in value.get("target_entity_ids", []) or []
            ),
            requires_explanation=bool(value.get("requires_explanation", False)),
        )


@dataclass(frozen=True)
class OrderInput:
    entity_id: str
    side: Literal["BUY", "SELL", "HOLD"]
    filled_quantity: float = 0.0
    filled_price: float = 0.0

    @property
    def absolute_notional(self) -> float:
        return abs(self.filled_quantity * self.filled_price)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "OrderInput":
        side = str(value.get("side", "HOLD")).upper()
        if side not in {"BUY", "SELL", "HOLD"}:
            side = "HOLD"
        return cls(
            entity_id=str(value.get("entity_id") or value.get("stock_code") or ""),
            side=side,  # type: ignore[arg-type]
            filled_quantity=float(value.get("filled_quantity", value.get("quantity", 0)) or 0),
            filled_price=float(value.get("filled_price", value.get("price", 0)) or 0),
        )


@dataclass(frozen=True)
class HoldingInput:
    entity_id: str
    quantity: float = 0.0
    market_price: float = 0.0
    weight: float | None = None

    @property
    def market_value(self) -> float:
        return abs(self.quantity * self.market_price)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "HoldingInput":
        weight_value = value.get("weight")
        return cls(
            entity_id=str(value.get("entity_id") or value.get("stock_code") or ""),
            quantity=float(value.get("quantity", 0) or 0),
            market_price=float(value.get("market_price", value.get("price", 0)) or 0),
            weight=float(weight_value) if weight_value is not None else None,
        )


@dataclass(frozen=True)
class DecisionInput:
    session_id: str
    scenario_id: str
    scenario_version: int
    turn_no: int
    answers: tuple[AnswerInput, ...]
    orders: tuple[OrderInput, ...] = ()
    portfolio_before: tuple[HoldingInput, ...] = ()
    portfolio_after: tuple[HoldingInput, ...] = ()
    visible_claim_ids: tuple[str, ...] = ()
    dependency_diagnostics: tuple[dict[str, Any], ...] = ()

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "DecisionInput":
        return cls(
            session_id=str(value.get("session_id", "")),
            scenario_id=str(value.get("scenario_id", "")),
            scenario_version=int(value.get("scenario_version", 1)),
            turn_no=int(value.get("turn_no", 0)),
            answers=tuple(AnswerInput.from_dict(item) for item in value.get("answers", [])),
            orders=tuple(OrderInput.from_dict(item) for item in value.get("orders", [])),
            portfolio_before=tuple(
                HoldingInput.from_dict(item) for item in value.get("portfolio_before", [])
            ),
            portfolio_after=tuple(
                HoldingInput.from_dict(item) for item in value.get("portfolio_after", [])
            ),
            visible_claim_ids=tuple(str(item) for item in value.get("visible_claim_ids", [])),
            dependency_diagnostics=tuple(value.get("dependency_diagnostics", []) or []),
        )

    def to_snapshot_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    answer_id: str
    sentence_index: int
    character_start: int
    character_end: int
    evidence_span: str
    factor_id: str
    scope: str
    entity_ids: tuple[str, ...]
    direction: str
    certainty: str
    negated: bool
    extractor_sources: tuple[str, ...]
    model_confidence: float
    validation_status: ValidationStatus
    extractor_version: str
    diagnostic_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RelationEvidence:
    relation_evidence_id: str
    source_evidence_id: str
    target_evidence_id: str
    relation: str
    sign: str
    connector_span: str
    sentence_distance: int
    explicitness: str
    model_confidence: float
    matched_edge_ids: tuple[str, ...]
    validation_status: ValidationStatus
    relation_extractor_version: str
    diagnostic_codes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PathMatch:
    path_id: str
    applicability: str
    status: str
    recognized_segment_ids: tuple[str, ...]
    missing_segment_ids: tuple[str, ...]
    recognized_node_ids: tuple[str, ...]
    recognized_edge_ids: tuple[str, ...]
    relation_evidence_ids: tuple[str, ...]
    industry_to_stock_link: str
    diagnostic_tags: tuple[str, ...]
    segment_coverage: float
    target_entity_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FeedbackItem:
    code: str
    severity: Literal["SUCCESS", "INFO", "WARNING", "ERROR"]
    path_id: str | None
    entity_ids: tuple[str, ...]
    segment_ids: tuple[str, ...]
    claim_ids: tuple[str, ...]
    template_key: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
