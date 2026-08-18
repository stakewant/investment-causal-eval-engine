# 인과 요인 그래프 스키마 v1

- 문서 ID: `CAUSAL_FACTOR_GRAPH_SCHEMA_V1`
- 스키마 버전: `causal-factor-graph-v1.1`
- 상태: 개정 기준안, 신규 엔진 `SHADOW` 전용
- 적용 대상: Scenario Compiler, Evidence Extractor, Relation Extractor, Graph Matcher, M6 Scorer
- 핵심 원칙: 직접·간접과 역할은 요인의 고정 속성이 아니라 특정 사건·대상·경로·시간에서 형성되는 속성이다.

## 1. 목적

평면 요인 목록으로는 사용자가 산업을 맞게 봤지만 종목을 잘못 고른 경우, 직접 노출은 봤지만 간접 전달을 놓친 경우, 관련 단어는 나열했지만 인과 연결은 하지 못한 경우를 안정적으로 구분하기 어렵다.

이 스키마는 다음을 분리한다.

- 공통 요인 개념과 별칭
- 턴별 노드와 시간 유효성
- 경로 안에서의 역할
- 관계 자체의 사용자 증거와 출처 근거
- 채점에 필요한 의미 구간
- 시장·포트폴리오 조정 조건

## 2. 범위와 경로 역할

### 2.1 범위 `scope`

| 값 | 의미 |
|---|---|
| `MARKET` | 전체 시장·거시 환경 |
| `INDUSTRY` | 산업·섹터 수준 |
| `STOCK` | 개별 기업·종목 수준 |
| `PORTFOLIO` | 사용자 포트폴리오 수준 |

### 2.2 경로 역할 `path_node_role`

| 값 | 의미 |
|---|---|
| `TRIGGER` | 사건의 출발점 |
| `DIRECT_EXPOSURE` | 대상 가치에 직접 연결되는 노출 |
| `CAUSAL_MEDIATOR` | 사건이 전달되는 중간 경로 |
| `PARALLEL_CONTEXT` | 같은 시점에 함께 고려할 독립 요인 |
| `MARKET_MODIFIER` | 선반영·추세·변동성 등 행동 강도 조정 조건 |
| `PORTFOLIO_CONSTRAINT` | 현금·집중도·기존 보유량 등 사용자 제약 |
| `TARGET_OUTCOME` | 실적·가치·수급·위험 등 목표 결과 |

공통 `factor_catalog`에는 `allowed_roles`만 저장한다. 실제 역할은 `CausalPath.path_nodes[].path_node_role`에 저장한다. 같은 요인이 경로 A에서는 `CAUSAL_MEDIATOR`, 경로 B에서는 `MARKET_MODIFIER`여도 모순이 아니다.

## 3. 직접·간접 판정

- `DIRECT`: 대상 종목의 매출·비용·재무·가치·수급으로 한 경제 단계에 연결된다.
- `INDIRECT`: 대상 결과까지 하나 이상의 의미 있는 경제적 전달 구간을 거친다.
- `PARALLEL`: 원사건에서 파생됐다고 단정하지 않지만 같은 판단에 필요하다.
- `MODIFIER`: 방향을 새로 만들기보다 확률·강도·행동 범위를 조정한다.

단순 문장 수나 그래프 노드 수로 직접·간접을 결정하지 않는다. 경로에 선언된 `semantic_segments`와 대상까지의 경제적 전달 구조로 판정한다.

## 4. 공통 요인 카탈로그

```json
{
  "factor_id": "HBM_DEMAND_GROWTH",
  "label": "HBM 수요 증가",
  "description": "AI 가속기와 서버 확대로 고대역폭 메모리 수요가 증가하는 상태",
  "aliases": ["HBM 수요 증가", "고대역폭 메모리 수요 확대"],
  "entity_types": ["INDUSTRY", "STOCK"],
  "allowed_roles": ["DIRECT_EXPOSURE", "CAUSAL_MEDIATOR"],
  "direction_patterns": {
    "POSITIVE": ["증가", "확대", "성장"],
    "NEGATIVE": ["감소", "둔화", "위축"]
  },
  "negation_patterns": ["아니다", "어렵다", "제한적이다"],
  "catalog_version": "factor-catalog-v1"
}
```

카탈로그의 의미·별칭·허용 역할은 공통 정의다. 턴별 중요도, 방향, 실제 역할, 직접·간접 분류는 그래프에 둔다.

## 5. 턴 그래프 노드

```json
{
  "node_id": "N-HBM-DEMAND",
  "factor_id": "HBM_DEMAND_GROWTH",
  "scope": "INDUSTRY",
  "entity_ids": ["SEMICONDUCTOR", "HBM"],
  "expected_direction": "POSITIVE",
  "importance": "REQUIRED | SUPPORTING | OPTIONAL",
  "available_from_turn": 1,
  "horizon": "SHORT | MEDIUM | LONG | TURN_DEFINED",
  "source_claim_refs": ["CLM-001"],
  "scoring_eligibility": "MANDATORY_ELIGIBLE | OPTIONAL_ELIGIBLE | FEEDBACK_ONLY",
  "as_of_justification_ref": "JUST-001"
}
```

### 노드 규칙

1. 한 노드는 하나의 표준 요인 ID를 참조한다.
2. 종목 노드는 `entity_ids`에 종목코드를 포함한다.
3. 필수 노드는 시간 정책의 필수 감점 허용식을 통과해야 한다.
4. 사후 자료에만 근거한 노드는 `OPTIONAL` 또는 `FINAL_REVIEW_ONLY`다.
5. 노드 자체의 `role` 필드는 금지한다. 실제 역할은 경로 노드에 둔다.

## 6. 인과 간선과 시간 유효성

```json
{
  "edge_id": "E-HBM-TO-HYNIX-SALES",
  "from_node": "N-HBM-DEMAND",
  "to_node": "N-HYNIX-HBM-SALES",
  "relation": "EXPOSES",
  "sign": "POSITIVE",
  "strength": "STRONG | MEDIUM | WEAK | CONDITIONAL",
  "lag": "IMMEDIATE | SHORT | MEDIUM | LONG",
  "importance": "REQUIRED | SUPPORTING | OPTIONAL",
  "conditions": [],
  "valid_from": "2024-01-01T00:00:00+09:00",
  "valid_to": null,
  "evidence_available_at": "2024-02-01T09:00:00+09:00",
  "source_claim_refs": ["CLM-002"],
  "temporal_status": "PUBLIC_AS_OF | NOT_PUBLIC_AS_OF | UNKNOWN",
  "scoring_eligibility": "MANDATORY_ELIGIBLE | OPTIONAL_ELIGIBLE | FEEDBACK_ONLY",
  "as_of_justification_ref": "JUST-002"
}
```

허용 관계는 `CAUSES`, `INCREASES`, `DECREASES`, `AMPLIFIES`, `MITIGATES`, `EXPOSES`, `PRICES_IN`, `CONTRADICTS`, `CONDITIONAL_ON`으로 시작한다.

필수 간선은 현재 컷오프에 유효하고 시간 정책을 통과한 source claim 또는 검수된 사전지식 근거를 가져야 한다.

## 7. 경로와 경로별 역할

```json
{
  "path_id": "AI_TO_HYNIX_EARNINGS",
  "label": "AI 투자에서 SK하이닉스 실적까지의 전달 경로",
  "path_class": "INDIRECT",
  "source_scope": "MARKET",
  "target_scope": "STOCK",
  "target_entity_ids": ["000660"],
  "path_nodes": [
    {"sequence": 1, "node_id": "N-AI-CAPEX", "path_node_role": "TRIGGER", "segment_id": "TRIGGER"},
    {"sequence": 2, "node_id": "N-HBM-DEMAND", "path_node_role": "CAUSAL_MEDIATOR", "segment_id": "INDUSTRY_TRANSMISSION"},
    {"sequence": 3, "node_id": "N-HYNIX-HBM-SALES", "path_node_role": "DIRECT_EXPOSURE", "segment_id": "TARGET_EXPOSURE"},
    {"sequence": 4, "node_id": "N-HYNIX-EARNINGS", "path_node_role": "TARGET_OUTCOME", "segment_id": "TARGET_OUTCOME"}
  ],
  "edge_ids": ["E-AI-TO-HBM", "E-HBM-TO-HYNIX-SALES", "E-SALES-TO-EARNINGS"],
  "required_semantic_segments": [
    {"segment_id": "TRIGGER", "one_of_node_ids": ["N-AI-CAPEX"]},
    {"segment_id": "INDUSTRY_TRANSMISSION", "one_of_node_ids": ["N-HBM-DEMAND"]},
    {"segment_id": "TARGET_EXPOSURE", "one_of_node_ids": ["N-HYNIX-HBM-SALES"]},
    {"segment_id": "TARGET_OUTCOME", "one_of_node_ids": ["N-HYNIX-EARNINGS"]}
  ],
  "alternative_group_id": "ALT-AI-HBM-BENEFIT",
  "importance": "REQUIRED",
  "applicability": "APPLICABLE | NOT_APPLICABLE",
  "feedback_release": "POST_TURN_AS_OF | FINAL_REVIEW_ONLY"
}
```

## 8. 그래프 복잡도 정규화

저자가 노드를 많이 쪼갠 시나리오가 더 어렵거나 더 낮게 채점되지 않도록 다음을 강제한다.

1. 채점 단위는 전체 노드 수가 아니라 `required_semantic_segments`다.
2. 필수 경로는 기본적으로 `TRIGGER`, `INDUSTRY_TRANSMISSION`, `TARGET_EXPOSURE`, `TARGET_OUTCOME`의 최대 네 의미 구간을 사용한다.
3. 한 의미 구간 안의 중간 노드는 대체 표현으로 묶고 전부를 필수화하지 않는다.
4. 중간 매개가 학습 목표인 턴만 `INDUSTRY_TRANSMISSION`을 독립 필수 구간으로 지정한다.
5. 경로별 필수 의미 구간 수는 4를 넘길 수 없고, 초과 시 compiler 오류다.
6. 동일 턴의 대체 경로는 동일한 필수 의미 구간 수와 유사한 난이도를 가져야 한다.
7. 신규 시나리오는 2인 저자 합의 또는 독립 재검수로 난이도 편차를 확인한다.

턴 그래프에는 다음을 기록한다.

```json
{
  "complexity_profile": {
    "required_segment_count": 4,
    "optional_mediator_count": 2,
    "difficulty_band": "FOUNDATION | INTERMEDIATE | ADVANCED",
    "author_review_status": "VERIFIED"
  }
}
```

## 9. 턴 그래프 계약

```json
{
  "schema_version": "causal-factor-graph-v1.1",
  "scenario_id": "semiconductor",
  "scenario_version": 1,
  "turn_no": 2,
  "market_date": "2024-02-22",
  "next_market_date": "2024-03-19",
  "learning_focus": ["INDUSTRY_TO_STOCK_CAUSALITY", "DIRECT_INDIRECT_BALANCE"],
  "rationale_prompt": "산업 영향과 선택한 종목의 실제 노출을 연결해 설명하세요.",
  "nodes": [],
  "edges": [],
  "paths": [],
  "market_modifier_node_ids": [],
  "portfolio_policy_ref": "PORT-SEM-T2-V1",
  "action_policy_ref": "ACTION-SEM-T2-V1",
  "source_policy_version": "temporal-source-v1.1",
  "graph_version": "semiconductor-v1-turn2-graph-v2"
}
```

## 10. 사용자 요인 증거 계약

```json
{
  "evidence_id": "EV-001",
  "sentence_index": 1,
  "character_start": 4,
  "character_end": 24,
  "evidence_span": "AI 서버 증가로 HBM 수요가 늘어난다",
  "factor_id": "HBM_DEMAND_GROWTH",
  "scope": "INDUSTRY",
  "entity_ids": ["HBM"],
  "direction": "POSITIVE",
  "certainty": "LIKELY",
  "negated": false,
  "extractor_sources": ["RULE", "EMBEDDING", "LLM", "NEURAL"],
  "model_confidence": 0.91,
  "validation_status": "SCORE_ELIGIBLE | FEEDBACK_ONLY | REVIEW_REQUIRED | REJECTED",
  "extractor_version": "neural-evidence-v0"
}
```

원문 span, factor ID, entity, 방향·부정·불확실성을 각각 검증한다. 모델 confidence만으로 `SCORE_ELIGIBLE`이 될 수 없다.

## 11. 관계 증거 계약 `RelationEvidence`

요인을 각각 언급한 것과 둘을 인과적으로 연결한 것은 다르므로 별도 객체로 저장한다.

```json
{
  "relation_evidence_id": "REV-001",
  "source_evidence_id": "EV-001",
  "target_evidence_id": "EV-002",
  "relation": "CAUSES",
  "sign": "POSITIVE",
  "connector_span": "증가해 매출이 늘어난다",
  "sentence_distance": 0,
  "explicitness": "EXPLICIT | IMPLICIT",
  "model_confidence": 0.84,
  "matched_edge_ids": ["E-HBM-TO-HYNIX-SALES"],
  "validation_status": "SCORE_ELIGIBLE | FEEDBACK_ONLY | REVIEW_REQUIRED | REJECTED",
  "relation_extractor_version": "neural-relation-v0"
}
```

두 요인 증거가 모두 존재해도 `RelationEvidence`가 없거나 검증에 실패하면 `DISCONNECTED`다. 암시 관계는 승인된 담화 규칙 또는 사람 라벨 없이는 감점 근거로 사용하지 않는다.

## 12. 경로 매칭 결과

```json
{
  "path_id": "AI_TO_HYNIX_EARNINGS",
  "applicability": "APPLICABLE | NOT_APPLICABLE",
  "status": "COMPLETE | PARTIAL | WRONG_DIRECTION | DISCONNECTED | MISSING",
  "recognized_segment_ids": [],
  "missing_segment_ids": [],
  "recognized_node_ids": [],
  "recognized_edge_ids": [],
  "relation_evidence_ids": [],
  "industry_to_stock_link": "VALID | WEAK | INVALID | MISSING",
  "diagnostic_tags": []
}
```

## 13. 새로운 경로 처리

| 상태 | 처리 |
|---|---|
| `ACCEPTED_CANONICAL` | 기준 경로로 채점 |
| `ACCEPTED_ALTERNATIVE` | 승인된 대체 경로로 동일하게 채점 |
| `REVIEW_REQUIRED` | 자동 가점·감점하지 않고 검토 큐에 저장 |
| `UNSUPPORTED_PATH` | 종목·사실 연결 근거 부족으로 진단 |
| `OVEREXTENDED_PATH` | 지나치게 먼 추측으로 진단 |

사람이 승인한 새 경로는 기존 평가를 수정하지 않고 다음 graph·bundle 버전에 추가한다.

## 14. Graph Compiler 검증

저작자가 만든 그래프는 런타임 전에 compiler를 통과해야 한다.

### 치명 오류

- 존재하지 않는 `factor_id`, node, edge, entity 또는 source claim 참조
- `allowed_roles`에 없는 `path_node_role`
- 순환 금지 경로의 cycle, 끊어진 경로, 순서가 뒤바뀐 edge
- `REQUIRED` 노드·간선의 시간 정책 또는 이중 검수 실패
- 필수 의미 구간 4개 초과
- `NOT_APPLICABLE` 경로를 M6 필수 요소로 지정
- `POST_TURN_AS_OF` 경로에 사후·결과 claim 포함
- 대체 경로의 대상 종목 또는 방향 모순

### 경고

- 선택 노드 과다, 낮은 출처 다양성, 지나치게 긴 간접 경로
- 같은 오류를 M1·M2·M5·M6에 중복 소유하도록 정의
- `difficulty_band`와 실제 필수 구간 수의 불일치

compiler는 정규화된 그래프와 `graph_compile_hash`를 출력한다. 치명 오류가 하나라도 있으면 shadow 평가에도 사용할 수 없다.

## 15. 학습형 계층

1. 다중과제 증거 추출기: span, factor ID, scope, 방향, 부정, 불확실성, entity를 공동 학습한다.
2. 관계 추출기: 증거 쌍의 관계를 분류하고 `RelationEvidence` 후보를 만든다.
3. 그래프 경로 랭커: 사용자 증거와 기준 그래프 정렬, 대체 경로 순위화, 누락 구간 후보를 제안한다.

학습형 모델은 후보를 만든다. 시간 정책, 원문 고정, Graph Compiler와 Validator를 통과한 후보만 점수에 사용한다. 모델 장애 시 규칙·별칭·임베딩 경로로 최소 기능을 유지한다.

## 16. 학습 데이터 게이트

| 단계 | 최소 권장 데이터 |
|---|---:|
| 다중과제 추출기 파일럿 | 검수 문장 300개, 주요 라벨별 양성 30개 이상 |
| 서비스 후보 추출기 | 검수 문장 1,000개, 주요 라벨별 양성 100개 이상 |
| 관계 추출기 파일럿 | 검수 증거 쌍 500개, 주요 관계별 양성 50개 이상 |
| 그래프 경로 랭커 | 여러 시나리오 검수 경로 1,000개 이상 |

학습·검증·테스트는 문장 무작위 분할이 아니라 사용자와 시나리오 단위로 분리한다.

## 17. 버전 필드

```json
{
  "factor_catalog_version": "factor-catalog-v1",
  "graph_schema_version": "causal-factor-graph-v1.1",
  "graph_version": "semiconductor-v1-turn2-graph-v2",
  "graph_compile_hash": "sha256:...",
  "extractor_version": "neural-evidence-v0",
  "relation_model_version": "neural-relation-v0",
  "validator_version": "evidence-validator-v1"
}
```

## 18. 필수 테스트

- 동일 요인이 두 경로에서 서로 다른 역할로 정상 컴파일되는가.
- 직접 경로만 존재하는 턴에서 간접 경로가 `NOT_APPLICABLE`인가.
- 노드 두 개를 나열하고 관계를 말하지 않은 답안이 `DISCONNECTED`인가.
- 복잡한 그래프와 단순 그래프가 같은 의미 구간 충족 시 같은 완성도를 받는가.
- 필수 간선의 source claim과 시간 유효성이 없으면 컴파일이 실패하는가.
- `REQUIRED` 사전지식 간선의 이중 검수가 없으면 컴파일이 실패하는가.
- 미래 claim을 포함한 `POST_TURN_AS_OF` 경로가 거부되는가.

## 19. 관련 문서

- [시간 제약형 출처 정책 v1](./TEMPORAL_SOURCE_POLICY_V1.md)
- [M6 영향 경로·대상 연결 채점 정책 v1](./M6_SCORING_POLICY_V1.md)
- [평가 엔진 연구 근거 및 관련 연구 v1](./RESEARCH_FOUNDATIONS_V1.md)




