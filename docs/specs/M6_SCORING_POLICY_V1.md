# M6 영향 경로·대상 연결 채점 정책 v1

- 문서 ID: `M6_SCORING_POLICY_V1`
- 정책 버전: `m6-scoring-v1.1`
- 신규 보조축: `M6_SCOPE_CAUSALITY`
- 상태: `SHADOW_ONLY`, 기존 총점·마이페이지 점수에 미반영
- 핵심 원칙: 산업 전망의 정오와 선택 종목까지의 실제 전달 경로 이해를 구분하되, 기존 M1~M5 오류를 다시 감점하지 않는다.

## 1. 목적

M6는 사용자가 사건의 산업 영향을 개별 종목의 사업·매출·비용·재무·가치·수급까지 연결했는지를 평가한다.

주요 교육 오류는 다음과 같다.

- 산업 전망을 관련 종목 모두의 동일 수혜로 일반화
- 종목의 직접 노출만 보고 중요한 간접 전달을 누락
- 산업·종목 단어는 함께 썼지만 인과 관계를 설명하지 못함
- 실제 사업 노출이 없는 종목을 수혜주로 단정

시장 상태와 포트폴리오를 행동 강도에 반영했는지는 M4가 소유한다. M6는 이를 진단 문맥으로만 표시한다.

## 2. 기존 축과 오류 소유권

| 오류·질문 | 주 소유 축 | M6 처리 |
|---|---|---|
| 필요한 핵심 요인을 발견했는가 | M1 | 누락 사실을 참고하되 중복 감점 금지 |
| 공개 사실·방향을 맞게 해석했는가 | M2 | 경로 상태에 표시하되 같은 사실 오류를 재감점 금지 |
| 위험·완화·불확실성을 균형 있게 봤는가 | M3 | 보조 진단만 |
| 근거와 체결·보유 행동이 일치하는가 | M4 | 점수 반영 금지 |
| 문장 내부의 원인→영향→행동 논리가 이어지는가 | M5 | 문장 일관성 재감점 금지 |
| 산업 요인이 이 종목에 어떤 노출·경로로 전달되는가 | M6 | 주 채점 대상 |

오류는 하나의 `error_owner`만 가진다. 다른 축에서는 `propagated_diagnostic=true`로 표시할 수 있지만 별도 감점을 만들 수 없다.

```json
{
  "error_code": "INDUSTRY_DIRECTION_REVERSED",
  "error_owner": "M2",
  "propagated_to": ["M6"],
  "m6_deduction_applied": false
}
```

## 3. shadow 운영 원칙

M6는 검증 전까지 기존 `beta-v3-cross-turn-coaching`의 총점에 합치지 않는다.

```text
동일한 TurnRecord
├─ beta-v3-cross-turn-coaching       사용자에게 보이는 현재 평가
└─ causal-evaluator shadow bundle    내부 비교용 M6 보조 평가
```

- 기존 M1~M5, 총점, 등급과 마이페이지 기록은 변경하지 않는다.
- M6가 승격되더라도 총점 가중치는 별도 정책·실험으로 승인한다.
- 사용자 요구였던 10% 이상 반영은 `SCORE_PREVIEW` 이후 검증할 후보값이며 v1.1 운영값이 아니다.

## 4. M6 상태와 점수 범위

M6 상태는 `SCORED`, `NOT_ASSESSED`, `NOT_APPLICABLE` 중 하나다.

- `SCORED`: 설명 의무가 있는 종목에 점수 가능한 증거가 존재한다.
- `NOT_ASSESSED`: 종목은 보유·체결했지만 이번 턴에 설명 의무가 없거나 답안이 종목을 다루지 않았다.
- `NOT_APPLICABLE`: 턴 학습목표에 종목 전달 경로가 없다.

`NOT_ASSESSED`와 `NOT_APPLICABLE`을 1점으로 바꾸지 않는다. 점수가 있는 경우에만 1.0~5.0을 사용한다.

## 5. 구성요소와 적용 가능성

M6는 중복을 줄이기 위해 두 구성요소만 가중한다.

| 구성요소 | 기본 가중치 | 질문 |
|---|---:|---|
| `target_exposure_reasoning` | 50% | 산업 변화가 이 종목의 어떤 사업·재무 노출에 닿는가 |
| `causal_transmission_reasoning` | 50% | 사건에서 대상 결과까지 어떤 직접·간접 관계로 이어지는가 |

시장·산업 방향 이해는 `industry_context_diagnostic`으로만 표시하고 M1·M2와 다시 가중하지 않는다. `industry_to_stock_link`는 별도 점수 구성요소가 아니라 M6의 유효성 gate와 cap으로 사용한다.

각 구성요소와 경로 클래스는 `APPLICABLE` 또는 `NOT_APPLICABLE`을 가진다. 적용 가능한 구성요소만 정규화한다.

```text
M6_base =
  Σ(component_score_i × configured_weight_i)
  / Σ(configured_weight_i for APPLICABLE components)
```

직접 경로만 존재하는 턴에서 간접 경로 누락으로 감점하지 않는다. 간접 경로가 턴 학습 목표일 때만 `causal_transmission_reasoning`의 간접 구간을 필수화한다.

## 6. 구성요소 앵커

### 6.1 대상 노출 이해 `target_exposure_reasoning`

| 점수 | 기준 |
|---:|---|
| 5 | 종목의 실제 제품·매출·비용·재무·수급 노출과 조건을 정확히 연결 |
| 4 | 핵심 노출은 맞지만 강도·조건 일부 누락 |
| 3 | 수혜·피해 종목임을 말했으나 구체 노출 근거가 약함 |
| 2 | 산업 전망을 종목에 단순 일반화 |
| 1 | 종목의 사업·재무 노출을 명백히 왜곡 |

### 6.2 인과 전달 이해 `causal_transmission_reasoning`

| 점수 | 기준 |
|---:|---|
| 5 | 적용 가능한 필수 의미 구간과 관계·방향을 모두 연결 |
| 4 | 핵심 경로는 맞지만 선택 구간 또는 조건 일부 누락 |
| 3 | 직접·간접 영향은 인식했지만 관계 하나가 약하거나 생략 |
| 2 | 관련 요인을 나열했지만 관계 증거가 없어 `DISCONNECTED` |
| 1 | 존재하지 않는 전달 경로 또는 대상 연결을 확정 |

직접·간접 하위 경로의 가중치는 답안을 본 뒤 정하지 않는다. 턴 그래프의 `learning_focus`와 `component_config`에 사전 고정한다.

## 7. 산업→종목 연결 gate

| 상태 | 처리 |
|---|---|
| `VALID` | M6 base 유지 |
| `WEAK` | 최대 3.5 |
| `MISSING` | 최대 3.0 |
| `INVALID` | 최대 2.5, `TARGET_EXPOSURE_FALSE`가 M6 소유일 때만 |

산업 방향 자체를 틀린 경우는 M2가 소유한다. M6에는 `DEPENDENCY_FAILED_M2`를 기록하고 그 사실 오류를 또 감점하지 않는다. 단, 산업 방향과 별개로 종목의 실제 노출을 허위로 연결한 오류는 M6가 소유한다.

## 8. 증거 등급과 관계 요건

| 등급 | 조건 | 점수 사용 |
|---|---|:---:|
| A `SCORE_ELIGIBLE` | 원문 span, 요인, entity, 방향, 시간, 그래프 검증 통과 | 허용 |
| B `FEEDBACK_ONLY` | 실제 문장은 있으나 대상·관계가 애매함 | 금지 |
| C `REVIEW_REQUIRED` | 기준에 없는 새 경로 | 금지 |
| D `REJECTED` | 원문에 없는 주장, 미래 정보, 허용되지 않은 요인 | 금지 |

요인 두 개를 각각 언급한 것만으로 경로를 인정하지 않는다. `RelationEvidence` 또는 승인된 명시 관계 규칙이 있어야 한다. 그렇지 않으면 `DISCONNECTED`다.

## 9. 경로 완성도

전체 노드 수가 아니라 인과 그래프의 필수 의미 구간으로 평가한다.

```text
사건 구간 → 산업 전달 구간 → 종목 노출 구간 → 종목 결과 구간
```

| 상태 | 의미 |
|---|---|
| `COMPLETE` | 적용 가능한 필수 구간과 방향·관계를 인식 |
| `PARTIAL` | 일부 필수 구간 누락 |
| `DISCONNECTED` | 요인은 언급했지만 관계를 말하지 않음 |
| `WRONG_DIRECTION` | 관계 방향을 반대로 해석; 사실 오류 소유권은 M2와 조정 |
| `MISSING` | 경로를 인식하지 못함 |
| `NOT_APPLICABLE` | 해당 턴에 이 경로 클래스가 없음 |

## 10. 종목 평가 대상 선정

### 10.1 후보 풀

- 질문이 명시한 종목
- 사용자 답안이 인과적으로 언급한 종목
- 실제 체결로 절대 비중 변화가 가장 큰 종목
- 턴 종료 후 비중이 가장 큰 보유 종목

최대 세 개 핵심 종목만 자동 평가 후보로 선택한다. 우선순위는 질문 지정 → 명시적 근거 → 최대 체결 변화 → 최대 보유 비중이다.

### 10.2 설명 의무와 `NOT_ASSESSED`

다음 중 하나일 때만 M6 설명 의무가 있다.

1. 질문이 해당 종목의 이유를 요구했다.
2. 사용자가 해당 종목과 요인을 명시적으로 연결했다.
3. 턴 정책이 최대 체결 변화 종목의 근거 입력을 필수로 지정했다.

큰 종목을 보유했다는 사실만으로 M6 설명 의무가 생기지 않는다. 언급하지 않은 보유종목은 `NOT_ASSESSED`로 기록하고 M6를 낮추지 않는다. HOLD와 과도한 집중은 M4 또는 포트폴리오 평가가 소유한다.

## 11. 종목별·턴별 종합

### 11.1 사고력 M6

설명 의무가 있고 `SCORED`인 종목만 종합한다. 종목 가중치는 답안을 보기 전 질문·턴 정책에 고정하며, 기본값은 동일 가중이다.

```text
Turn reasoning M6 =
  Σ(asset_M6_i × assessment_weight_i)
  / Σ(assessment_weight_i for SCORED assets)
```

평가 종목이 하나도 없으면 `Turn M6 = NOT_ASSESSED`다. 소액 주문에 최소 10%를 강제로 부여하는 공식은 사용하지 않는다.

### 11.2 노출 진단

실제 체결 변화와 보유 비중을 사용한 `exposure_weighted_diagnostic`은 별도로 계산할 수 있다. 이는 "틀린 경로에 자산을 얼마나 노출했는가"를 보여 주지만 사고력 M6와 기존 총점에는 영향을 주지 않는다.

```json
{
  "reasoning_m6": 3.4,
  "exposure_weighted_diagnostic": {
    "risk_level": "HIGH",
    "unsupported_exposure_ratio": 0.42
  }
}
```

## 12. cap 적용 순서

적용 순서는 고정한다.

```text
1. 적용 가능한 구성요소 점수 산출
2. 가중치 재정규화 후 M6_base 계산
3. M6 소유 사실 오류·산업→종목 연결 cap 적용
4. 입력 품질 cap 적용
5. 1.0~5.0 clamp
6. 소수 첫째 자리 반올림
```

cap은 가장 낮은 상한을 선택하며 모두 정책 ID와 함께 저장한다.

| 정책 ID | 조건 | 상한 |
|---|---|---:|
| `M6-CAP-TARGET-FALSE-01` | 종목 실제 노출을 명백히 왜곡 | 2.5 |
| `M6-CAP-SCOPE-WEAK-01` | 산업→종목 연결이 약함 | 3.5 |
| `M6-CAP-SCOPE-MISSING-01` | 산업→종목 연결이 없음 | 3.0 |
| `M6-CAP-LIST-ONLY-01` | 용어만 나열하고 관계 없음 | 3.0 |
| `M6-CAP-WEAK-INPUT-01` | `WEAK_RATIONALE` | 3.5 |
| `M6-CAP-INSUFFICIENT-INPUT-01` | `INSUFFICIENT_RATIONALE` | 2.0 |

```json
{
  "caps_applied": [
    {"policy_id": "M6-CAP-SCOPE-WEAK-01", "max_score": 3.5, "evidence_ids": ["EV-01"]}
  ]
}
```

## 13. 시장 상태·행동과 M4의 경계

경로가 정확해도 이미 급등했고 보유 비중이 과도하다면 M6는 높고 M4는 낮을 수 있다. `MARKET_STATE_IGNORED`, `OVERCONCENTRATED`, `RATIONALE_ACTION_MISMATCH`는 M4가 소유하며 M6 피드백에는 보조 문맥으로만 표시한다.

## 14. 턴 피드백 공개

진행 중 턴 피드백은 현재 `information_cutoff_at`까지 공개된 AS_OF claim만 사용한다.

```text
✓ 정확히 인식
△ 일부 연결
✕ 대상 연결 오류
○ 누락
? 검토가 필요한 새 경로
— 이번 턴 평가 대상 아님
```

사후 분석과 실제 결과는 시나리오 종료 후 복기에서만 역할을 명시해 공개한다. 진행 중 턴에는 다음 턴 사건·가격·결말을 포함하지 않는다.

## 15. 출력 계약 예시

```json
{
  "m6_policy_version": "m6-scoring-v1.1",
  "status": "SCORED",
  "components": {
    "target_exposure_reasoning": {"status": "APPLICABLE", "score": 2.5, "configured_weight": 0.5},
    "causal_transmission_reasoning": {"status": "APPLICABLE", "score": 3.5, "configured_weight": 0.5}
  },
  "industry_context_diagnostic": {"status": "CORRECT", "score_effect": 0},
  "industry_to_stock_link": "WEAK",
  "base_m6": 3.0,
  "caps_applied": [
    {"policy_id": "M6-CAP-SCOPE-WEAK-01", "max_score": 3.5}
  ],
  "final_m6": 3.0,
  "legacy_score_effect": 0,
  "evaluation_mode": "SHADOW"
}
```

## 16. evaluator bundle과 저장 키

`evaluator_version` 문자열 하나로 재현성을 보장하지 않는다. 다음을 불변 결합한 bundle을 만든다.

```json
{
  "evaluator_bundle_id": "ceval-bundle-2026-08-19-001",
  "bundle_hash": "sha256:...",
  "members": {
    "m6_policy_version": "m6-scoring-v1.1",
    "source_policy_version": "temporal-source-v1.1",
    "factor_catalog_version": "factor-catalog-v1",
    "graph_schema_version": "causal-factor-graph-v1.1",
    "graph_version": "semiconductor-v1-turn2-graph-v2",
    "graph_compile_hash": "sha256:...",
    "extractor_version": "neural-evidence-v0",
    "relation_extractor_version": "neural-relation-v0",
    "graph_ranker_version": null,
    "validator_version": "evidence-validator-v1",
    "llm_parser_version": "rationale-parser-v1"
  }
}
```

유일 키는 다음이다.

```text
(session_id, turn_no, evaluator_bundle_id, input_snapshot_hash)
```

bundle 구성요소가 하나라도 바뀌면 기존 ID를 재사용하지 않는다. 기존 평가를 덮어쓰지 않고 새 shadow record를 생성한다.

## 17. 학습형 엔진 단계

1. 규칙·별칭·금융 임베딩·LLM 구조화 후보를 결합한다.
2. 한국어 다중과제 신경망으로 span, factor, scope, 방향, entity를 추출한다.
3. 관계 추출기로 증거 쌍의 인과 관계를 만든다.
4. 데이터가 충분해지면 그래프 모델로 정렬·대체 경로를 순위화한다.
5. 자체 시간 Validator, Graph Matcher와 점수 정책이 최종 결과를 확정한다.

LLM과 학습 모델은 후보를 만들며 임의로 점수·경로·종목을 확정하지 않는다.

## 18. shadow 승격 기준

| 항목 | 초기 목표 |
|---|---:|
| 요인 추출 Macro-F1 | 0.80 이상 |
| 산업·종목 scope 분류 Macro-F1 | 0.85 이상 |
| 주요 인과관계 F1 | 0.75 이상 |
| M6 사람 평가 QWK | 0.70 이상 |
| 기존 M1~M5 MAE | 유의한 악화 없음 |
| 미래 정보 누수 | 0건 |
| 피드백 사람 선호율 | 70% 이상 |

승격 순서는 `SHADOW → INTERNAL_REVIEW → FEEDBACK_ONLY → SCORE_PREVIEW → PRIMARY`다. `PRIMARY` 전에 기존 평가 삭제, 자동 재평가 또는 총점 혼합을 하지 않는다.

## 19. 필수 테스트

- 산업은 맞고 종목 노출이 틀린 답안이 부분점수를 받되 고득점하지 않는가.
- 종목은 맞지만 산업 방향을 틀린 오류가 M2와 M6에서 중복 감점되지 않는가.
- 직접 경로만 존재하는 턴에서 간접 경로가 `NOT_APPLICABLE`이고 감점이 없는가.
- 큰 보유종목을 언급하지 않았을 때 `NOT_ASSESSED`이며 자동 1점이 아닌가.
- 질문 지정 종목을 설명하지 않았을 때만 설명 의무 미충족으로 처리하는가.
- 다종목 답안에서 최대 세 종목만 정책 순서대로 선정되는가.
- 용어 나열만 한 답안이 `DISCONNECTED`와 cap을 받는가.
- M1·M2·M4·M5 소유 오류가 M6 점수에서 다시 차감되지 않는가.
- cap 적용 순서와 반올림이 항상 동일한가.
- bundle 구성요소 변경 시 새로운 `evaluator_bundle_id`가 필요한가.
- shadow 결과가 기존 총점·등급·마이페이지를 변경하지 않는가.
- 턴 피드백에 사후 분석·미래 결과가 포함되지 않는가.

## 20. 관련 문서

- [시간 제약형 출처 정책 v1](./TEMPORAL_SOURCE_POLICY_V1.md)
- [인과 요인 그래프 스키마 v1](./CAUSAL_FACTOR_GRAPH_SCHEMA_V1.md)
- [평가 엔진 연구 근거 및 관련 연구 v1](./RESEARCH_FOUNDATIONS_V1.md)




