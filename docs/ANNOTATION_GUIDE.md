# 금융 투자근거 사람 주석 지침

## 주석 단위

한 레코드는 한 사용자의 한 턴 자유서술 답안이다. 같은 사용자의 같은 시나리오 답안은 모두 같은 train/validation/test split에 둔다.

## 1단계: Evidence span

원문에서 의미를 판단한 최소 연속 구간을 선택한다. 조사까지 포함할 필요는 없지만 방향 표현이 factor label 밖에 있으면 함께 보존할 수 있다.

필수 라벨:

- `factor_id`: catalog의 표준 요인
- `scope`: `MARKET`, `INDUSTRY`, `STOCK`, `PORTFOLIO`
- `entity_ids`: 명시되거나 질문 문맥으로 확정되는 대상
- `direction`: `POSITIVE`, `NEGATIVE`, `MIXED`, `CONDITIONAL`
- `certainty`: 단정, 가능성, 조건부
- `negated`: 부정 여부

원문에 없는 내용을 상식으로 보완해 span을 만들지 않는다. catalog에 없는 타당한 factor는 임의의 기존 ID로 맞추지 말고 새 factor 검토 큐에 기록한다.

## 2단계: RelationEvidence

두 factor를 각각 언급했다는 이유만으로 관계를 주석하지 않는다. 원인·영향·노출·완화·조건을 나타내는 표현이 원문에 있어야 한다.

- `source_evidence_id`, `target_evidence_id`
- 관계: `CAUSES`, `INCREASES`, `DECREASES`, `AMPLIFIES`, `MITIGATES`, `EXPOSES`, `PRICES_IN`, `CONDITIONAL_ON`
- 방향과 connector span
- `EXPLICIT` 또는 `IMPLICIT`

쉼표로 요인을 나열한 답안은 관계가 아니다. 문맥상 추론은 가능하지만 문장에 연결이 없으면 `IMPLICIT`로 두고 자동 채점에서 제외한다.

## 3단계: 경로와 M6

Graph Matcher 결과를 먼저 보지 않고 독립적으로 M6를 평가한 뒤 비교한다.

- 5: 종목의 실제 노출과 적용 가능한 전달 구간·조건을 정확히 연결
- 4: 핵심 경로는 맞고 일부 조건이나 보조 구간 누락
- 3: 종목 수혜·피해는 인식했으나 구체 노출 또는 관계가 약함
- 2: 산업 전망의 단순 일반화 또는 관계 없는 요인 나열
- 1: 존재하지 않는 종목 노출·전달경로를 확정

설명 의무가 없으면 `NOT_ASSESSED`, 해당 턴에 종목 전달 학습목표가 없으면 `NOT_APPLICABLE`로 두며 1점으로 바꾸지 않는다.

## 직접·간접 구분

factor 자체에 직접·간접 라벨을 붙이지 않는다. 대상 종목의 매출·비용·재무·수급으로 한 경제 단계에 닿으면 해당 경로에서 `DIRECT`, 의미 있는 전달 구간을 하나 이상 거치면 `INDIRECT`다.

## 이중 주석과 합의

파일럿과 test set은 최소 두 번 독립 주석한다. 불일치는 다음 순서로 해결한다.

1. 원문 span 경계
2. factor와 scope
3. relation과 방향
4. 경로 상태
5. M6 점수

합의 전 원주석을 덮어쓰지 않고 reviewer별 레코드를 유지한다. QWK, exact agreement와 ICC를 보고하며, 합의본은 별도 adjudicated dataset version으로 만든다.

## 품질 검사

`causal-engine validate-annotations`가 다음을 자동 검사한다.

- span이 원문과 정확히 일치하는가
- relation endpoint가 같은 답안의 evidence를 참조하는가
- M6가 1~5 범위인가
- 같은 사용자·시나리오가 여러 split에 섞였는가
- 주요 라벨의 양성 수가 충분한가
