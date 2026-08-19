# 독립 인과평가 엔진 아키텍처

## 목표

엔진은 자유서술 답안이 “산업이 좋아진다”에서 멈추지 않고 “그 변화가 선택 종목의 어떤 제품·매출·비용·재무 노출을 거쳐 어떤 결과로 이어지는가”를 설명했는지 평가한다. 결과 수익률이나 다음 턴 결말은 판단 과정 점수에 사용하지 않는다.

## 전체 흐름

```text
저작 단계
SourceClaim + FactorCatalog + TurnGraph
                  │
                  ▼
          Graph Compiler ── 실패 → 저작자 수정
                  │
                  ▼
       immutable EvaluatorBundle

평가 단계
DecisionInput + visible claim IDs
                  │
                  ▼
        TemporalPolicy / parser context
                  │
       ┌──────────┴──────────┐
       ▼                     ▼
 exact alias 후보      neural/LLM 후보(선택)
       └──────────┬──────────┘
                  ▼
        EvidenceValidator
                  │
                  ▼
     RelationExtractor/Validator
                  │
                  ▼
      semantic-segment GraphMatcher
                  │
       ┌──────────┴───────────┐
       ▼                      ▼
 M6 shadow scorer       novel-path review queue
       │                      └─ 자동 점수 효과 0
       ▼
 FeedbackPlan → OutputValidator → Korean renderer
```

## 신뢰 경계

학습 모델과 LLM은 후보만 생성한다. 다음은 결정할 수 없다.

- 최종 factor ID와 점수 가능 여부
- 공개 시점과 미래정보 허용 여부
- 기준 edge와 path의 존재
- M6 점수, cap, 기존 점수 효과
- 피드백에서 공개할 claim

원문 위치와 일치하지 않는 span, 기준 catalog에 없는 factor, 낮은 신뢰도, 암시 관계와 기준 edge가 없는 관계는 자동 점수에 사용되지 않는다. 기준에 없는 그럴듯한 경로는 `REVIEW_REQUIRED`로 저장하고 다음 graph version에서만 사람이 승인할 수 있다.

외부 모델은 `CandidateProvider`의 두 단계 계약으로 연결한다. 먼저 미래정보가 제거된 parser context에서 evidence 후보를 만들고, 검증된 evidence를 받은 뒤 relation 후보를 만든다. `CachedCandidateProvider`는 neural·embedding·LLM 출력을 context hash와 함께 재생해 같은 후보로 오프라인 실험을 반복할 수 있다.

필수 감점 claim은 graph에 `VISIBLE_TO_USER`라고 적힌 것만으로 부족하다. 실제 `DecisionInput.visible_claim_ids`에도 존재하거나 승인된 사전지식이어야 하며, 그렇지 않으면 평가는 fail-closed로 중단된다.

## 직접·간접 영향

직접·간접은 factor의 고정 속성이 아니다. 같은 factor도 사건·대상·경로에 따라 역할이 바뀐다. `path_nodes[].path_node_role`과 `required_semantic_segments`가 해당 턴의 역할을 정의한다.

채점은 노드 수가 아니라 최대 네 의미 구간을 사용한다.

```text
TRIGGER → INDUSTRY_TRANSMISSION → TARGET_EXPOSURE → TARGET_OUTCOME
```

직접·간접 경로가 함께 필수이면 둘 다 사전 고정 가중치로 평가한다. 같은 의미의 대체 경로는 `alternative_group_id`로 묶고 가장 잘 정렬된 승인 경로 하나만 사용한다.

## M1~M5와의 경계

M6는 종목 노출과 전달경로를 소유한다. 산업 방향 오류가 M2에 기록됐다면 M6는 `DEPENDENCY_FAILED_M2`로 전파만 받고 같은 오류를 다시 감점하지 않는다. 행동 강도·집중도·근거와 체결의 불일치는 M4가 소유하며 M6의 노출 진단은 총점에 영향을 주지 않는다.

## 결정론과 감사

평가 레코드의 키는 `(session_id, turn_no, evaluator_bundle_id, input_snapshot_hash)`다. 출력에는 bundle 구성 버전, graph hash, source snapshot hash와 parser context hash가 기록된다. 동일 입력과 동일 bundle은 동일한 평가 레코드를 생성한다.

## 현재 비포함 범위

- 통합 Node/FastAPI 서버 호출
- 운영 DB 저장과 사용자 UI
- 수익률 예측 또는 경제적 인과효과 식별
- 데이터가 없는 상태에서의 한국어 대규모 신경망 가중치

이 항목들은 엔진 계약이 아니라 배포·데이터 수집 단계다.
