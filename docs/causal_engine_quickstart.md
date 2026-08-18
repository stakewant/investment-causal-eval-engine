# Causal Engine v2 shadow quickstart

## 목적

기존 M1~M5 연구 엔진을 교체하지 않고, 시간 제약형 인과경로 평가와 M6를 별도 shadow 경로에서 실험한다.

```text
기존 data/human_labels.csv
        └─ legacy rule_score.py → 현재 M1~M5 연구 결과

신규 source claims + factor catalog + turn graph
        └─ Graph Compiler → compiled graph → 이후 M6 shadow scorer
```

현재 단계에서는 Graph Compiler까지만 구현되어 있다. 사용자 답안 추출기와 M6 scorer는 다음 단계다.

설계 기준은 [docs/specs/README.md](specs/README.md)에 모아 두었다.

## 디렉터리

```text
schemas/                       기계 판독 JSON 계약
src/causal_engine/             신규 엔진 패키지
src/compile_causal_graph.py    컴파일 CLI
examples/semiconductor_turn2/  구조 검증용 fixture
tests/                         컴파일러 회귀 테스트
```

## 그래프 컴파일

```powershell
cd C:\dev\PycharmProjects\investment-causal-eval-engine

.\.venv\Scripts\python.exe src\compile_causal_graph.py `
  --catalog examples\semiconductor_turn2\factor_catalog.json `
  --claims examples\semiconductor_turn2\source_claims.json `
  --graph examples\semiconductor_turn2\graph.json `
  --output outputs\semiconductor_turn2.compiled.json
```

정상 출력:

```text
[OK] compiled graph: outputs\semiconductor_turn2.compiled.json
```

## 테스트

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

현재 회귀 테스트는 다음을 검사한다.

- 정상 fixture와 안정적인 compile hash
- 컷오프 이후 필수 claim 차단
- 끊어진 경로 차단
- factor에서 허용하지 않은 경로 역할 차단
- 필수 의미 구간 4개 초과 차단
- 진행 중 피드백의 사후 claim 차단
- 보이지 않은 필수 claim의 사전지식 검수 요구
- JSON Schema 문서 구문

## 운영 데이터 전환 조건

`examples/semiconductor_turn2`는 구조 fixture이며 실제 역사적 근거가 아니다. 운영 시나리오로 전환하려면 다음이 필요하다.

1. `source_type=FIXTURE`를 실제 뉴스·공시·시장 데이터로 교체한다.
2. 원문 span, URL, 공개시각을 검증한다.
3. 사용자 화면에 실제로 노출한 claim을 기록한다.
4. 필수 사전지식 경로는 두 명의 검수를 받는다.
5. `author_review_status=VERIFIED`로 승격한다.

## 다음 구현

1. 사용자 답안 `Evidence`·`RelationEvidence` 입력 fixture
2. deterministic Graph Matcher
3. M6 `SCORED`·`NOT_ASSESSED`·`NOT_APPLICABLE` 계산
4. 기존 M1~M5와 병렬 실행하는 shadow runner

