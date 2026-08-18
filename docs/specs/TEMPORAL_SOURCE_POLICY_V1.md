# 시간 제약형 출처 정책 v1

- 문서 ID: `TEMPORAL_SOURCE_POLICY_V1`
- 정책 버전: `temporal-source-v1.1`
- 상태: 개정 기준안, 신규 엔진 `SHADOW` 전용
- 적용 대상: 시나리오 제작, 사용자 화면, 턴 평가, 턴 피드백, 최종 복기
- 핵심 원칙: 공개된 정보, 실제로 사용자에게 보인 정보, 채점 가능한 정보를 서로 구분한다.

## 1. 목적

사후 애널리스트 보고서와 후속 실적 자료는 역사적 사건의 인과 경로를 복원하는 데 유용하다. 그러나 그 내용을 당시 정보처럼 노출하거나 사용자의 필수 인식 요인으로 삼으면 미래 정보 누수가 발생한다.

이 정책은 다음을 보장한다.

1. 사용자는 현재 턴까지 실제로 공개된 정보만 받는다.
2. 필수 감점은 실제 노출 정보 또는 사전에 승인된 일반 지식만으로 발생한다.
3. 사후 분석과 실제 결과는 시나리오 진행 중 피드백에 사용하지 않는다.
4. 출처 역할을 문서 전체가 아니라 개별 주장 단위로 판정한다.
5. 추출기·LLM·피드백 렌더러가 같은 정보 경계를 사용한다.
6. 모든 판단은 출처 claim과 evaluator bundle로 재현할 수 있다.

## 2. 시간 필드

| 필드 | 의미 |
|---|---|
| `event_at` | 사건이 실제로 발생한 시각 |
| `published_at` | 문서가 발행된 시각 |
| `available_at` | 일반 사용자가 해당 claim을 확인할 수 있게 된 시각 |
| `information_cutoff_at` | 현재 턴에서 허용되는 정보 상한 시각 |
| `visible_at` | 시스템이 사용자 화면에 해당 claim을 실제 표시한 시각 |
| `valid_from` / `valid_to` | claim이 설명하는 사실의 유효 구간 |
| `observed_at` | 가격·지표가 관측된 시각 |

`PUBLIC_AS_OF`의 기본 판정은 `available_at <= information_cutoff_at`이다. 시각을 알 수 없고 날짜만 확인되는 출처는 보수적으로 해당 날짜의 시장 종료 이후 공개된 것으로 처리한다.

## 3. 공개·노출·채점 가능성의 분리

각 claim은 다음 세 상태를 독립적으로 가진다.

| 축 | 값 | 의미 |
|---|---|---|
| 공개 상태 | `PUBLIC_AS_OF`, `NOT_PUBLIC_AS_OF`, `UNKNOWN` | 당시 외부에서 알 수 있었는가 |
| 노출 상태 | `VISIBLE_TO_USER`, `NOT_VISIBLE_TO_USER` | 현재 세션에서 실제로 보여 주었는가 |
| 채점 상태 | `MANDATORY_ELIGIBLE`, `OPTIONAL_ELIGIBLE`, `FEEDBACK_ONLY`, `INELIGIBLE` | 점수에 어떻게 사용할 수 있는가 |

### 3.1 필수 감점 허용식

```text
mandatory_deduction_allowed =
  public_status == PUBLIC_AS_OF
  AND (
    visibility_status == VISIBLE_TO_USER
    OR prior_knowledge.status == APPROVED
  )
  AND scoring_eligibility == MANDATORY_ELIGIBLE
```

화면에 보이지 않은 공개 정보는 자동으로 필수 감점 근거가 되지 않는다. `prior_knowledge.status=APPROVED`로 인정하려면 해당 지식이 학습 목표에 명시돼 있고, 당시 일반적으로 추론 가능하며, 사람 검수를 통과해야 한다.

화면에 보이지 않았고 승인된 사전지식도 아닌 claim은 `OPTIONAL_ELIGIBLE` 보너스 또는 `FEEDBACK_ONLY`로만 사용할 수 있다.

## 4. claim 단위 지식 역할

한 문서 안에 당시 공개 사실, 사후 해석, 이후 결과가 섞일 수 있으므로 `knowledge_role`은 `SourceDocument`가 아니라 `SourceClaim`에 부여한다.

### 4.1 `AS_OF_EVIDENCE`

현재 컷오프 이전에 공개된 사실·해석이다. 공개 상태와 노출·사전지식 조건을 추가로 충족할 때만 점수에 사용할 수 있다.

### 4.2 `RETROSPECTIVE_ANALYSIS`

현재 컷오프 이후 작성된 인과 해설이다. 그래프 후보 발굴과 시나리오 종료 후 복기에만 사용한다. 진행 중 턴의 사용자 입력, M1~M6, 턴 피드백에는 사용하지 않는다.

### 4.3 `OUTCOME_EVIDENCE`

이후 가격, 수익률, 실적, 인수·파산·정책 결과다. 포트폴리오 결과와 시나리오 종료 후 복기에만 사용한다. 판단 과정 점수의 입력으로 사용하지 않는다.

## 5. 단계별 허용 행렬

| 용도 | AS_OF | RETROSPECTIVE | OUTCOME |
|---|:---:|:---:|:---:|
| 턴 시작 전 사용자 노출 | 조건부 허용 | 금지 | 금지 |
| 사용자 답안 파서 컨텍스트 | 허용 claim만 | 금지 | 금지 |
| M1~M6 계산 | 채점 가능 claim만 | 금지 | 금지 |
| 인과 그래프 후보 발굴 | 허용 | 허용 | 조건부 허용 |
| 진행 중 턴 종료 피드백 | 현재 컷오프 claim만 | 금지 | 금지 |
| 시나리오 종료 후 전체 복기 | 허용 | 허용, 사후 분석 표기 | 허용, 결과 표기 |
| 내부 저작·검수 도구 | 허용 | 허용 | 허용 |

진행 중 턴의 `POST_TURN_FEEDBACK`은 시나리오가 끝난 뒤의 `FINAL_REVIEW`와 다르다. 현재 턴을 제출했더라도 미래 턴이 남았다면 사후 분석과 결과 정보는 여전히 금지한다.

## 6. 출처·claim 계약

```json
{
  "source_id": "SRC-SVB-001",
  "source_type": "NEWS | FILING | ANALYST_REPORT | MARKET_DATA | RESEARCH | OUTCOME",
  "title": "자료 제목",
  "publisher": "발행처",
  "source_url": "https://example.com",
  "content_hash": "sha256:...",
  "source_version": 1,
  "claims": [
    {
      "claim_id": "CLM-SVB-001-03",
      "text": "채권 평가손실이 자본 부담을 확대했다",
      "evidence_span": "원문에서 검증 가능한 구간",
      "event_at": "2023-03-10T00:00:00+09:00",
      "published_at": "2023-03-20T09:00:00+09:00",
      "available_at": "2023-03-20T09:00:00+09:00",
      "valid_from": "2023-03-10T00:00:00+09:00",
      "valid_to": null,
      "knowledge_role": "RETROSPECTIVE_ANALYSIS",
      "public_status": "NOT_PUBLIC_AS_OF",
      "visibility_status": "NOT_VISIBLE_TO_USER",
      "scoring_eligibility": "FEEDBACK_ONLY",
      "allowed_uses": ["GRAPH_AUTHORING", "FINAL_REVIEW"]
    }
  ]
}
```

원문을 저장할 수 없는 경우에도 제목, 발행처, URL, 공개 시각, 사용한 요약, 수집 시각과 콘텐츠 해시를 남긴다. 문서 역할을 claim 역할의 대용으로 사용해서는 안 된다.

## 7. `as_of_justified` 검수 계약

사후 자료에서 발견했지만 당시 일반 지식으로 추론 가능했다고 주장하는 노드·간선은 단순한 boolean으로 승인할 수 없다.

```json
{
  "as_of_justification": {
    "status": "VERIFIED",
    "justification_type": "VISIBLE_EVIDENCE | APPROVED_PRIOR_KNOWLEDGE | INDEPENDENT_AS_OF_SOURCE",
    "justification_text": "당시 공개 자료와 일반 산업 구조로 추론 가능한 이유",
    "policy_rule_id": "TSV1-R-MANDATORY-02",
    "reviewers": [
      {"reviewer_id": "R01", "reviewed_at": "2026-08-19T10:00:00+09:00"},
      {"reviewer_id": "R02", "reviewed_at": "2026-08-19T11:00:00+09:00"}
    ]
  }
}
```

- `REQUIRED` 노드·간선에는 서로 다른 두 검수자의 승인 또는 시간 간격을 둔 독립 재검수가 필요하다.
- `SUPPORTING`은 한 명의 승인으로 둘 수 있다.
- 검수가 없거나 `PENDING`이면 `OPTIONAL` 또는 `FINAL_REVIEW_ONLY`다.
- 사후 자료만 존재한다는 사실만으로 `APPROVED_PRIOR_KNOWLEDGE`가 될 수 없다.

## 8. 런타임 모델 경계

사용자 답안 파서에는 다음만 제공한다.

- 사용자 자유서술
- 현재 턴까지 공개된 엔터티와 요인 별칭
- 현재 턴의 허용된 `AS_OF_EVIDENCE` claim
- 실제 사용자 화면에 노출된 claim ID

다음은 제공하지 않는다.

- 사후 분석 원문·요약
- 이후 턴 뉴스·가격·결말
- 정답 점수, 감점값, 숨겨진 필수 경로
- `OUTCOME_EVIDENCE`

LLM 피드백 렌더러는 엔진이 확정한 `FeedbackPlan`만 문장화한다. 점수, 종목, 경로, 행동 코드와 정보 시점을 바꿀 수 없다.

## 9. 출력 검증과 실패 처리

`OutputValidator`는 다음을 검사한다.

1. 컷오프 이후 날짜·사건·가격이 포함됐는가.
2. 허용되지 않은 claim 또는 `FeedbackPlan`에 없는 사실·종목을 추가했는가.
3. 사후 분석을 당시 확정 사실로 표현했는가.
4. 점수·경로 상태·행동 코드를 변경했는가.

검증에 실패하면 현재 컷오프 claim만 사용하는 템플릿 피드백으로 대체하고 `TEMPORAL_OUTPUT_REJECTED`를 기록한다.

## 10. 저장·재현 계약

```json
{
  "source_policy_version": "temporal-source-v1.1",
  "source_snapshot_hash": "sha256:...",
  "information_cutoff_at": "2023-03-10T23:59:59+09:00",
  "visible_claim_ids": [],
  "mandatory_claim_ids": [],
  "optional_claim_ids": [],
  "authoring_only_claim_ids": [],
  "final_review_claim_ids": []
}
```

정책, claim 판정 또는 컷오프가 바뀌면 기존 평가를 덮어쓰지 않는다. M6 문서의 `evaluator_bundle_id`를 새로 만들고 새로운 shadow 평가로 저장한다.

## 11. 필수 테스트

- 같은 문서의 AS_OF claim과 RETROSPECTIVE claim이 서로 다른 용도로 분리되는가.
- 공개됐지만 화면에 보이지 않은 claim이 승인 없이 필수 감점을 만들지 않는가.
- 승인된 사전지식에는 규칙 ID와 검수 기록이 존재하는가.
- 컷오프 직후 발행된 claim이 턴 입력에서 제외되는가.
- 날짜만 있는 출처가 보수적으로 처리되는가.
- 턴 3 피드백이 턴 4 사건·가격·사후 분석을 노출하지 않는가.
- 시나리오 종료 후 복기에서만 RETROSPECTIVE·OUTCOME이 역할 표기와 함께 공개되는가.
- LLM 파서 입력 스냅샷에 미래 정보가 없는가.
- LLM 렌더러가 미래 사실을 추가하면 템플릿으로 대체되는가.

## 12. 관련 문서

- [인과 요인 그래프 스키마 v1](./CAUSAL_FACTOR_GRAPH_SCHEMA_V1.md)
- [M6 영향 경로·대상 연결 채점 정책 v1](./M6_SCORING_POLICY_V1.md)
- [평가 엔진 연구 근거 및 관련 연구 v1](./RESEARCH_FOUNDATIONS_V1.md)




