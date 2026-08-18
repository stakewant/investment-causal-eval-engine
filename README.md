# Investment Causal Evaluation Engine

투자 시나리오에서 사용자의 자유서술 근거를 시점별 인과경로에 정렬하고, 직접·간접 영향과 종목 노출 이해를 평가하기 위한 독립 연구·개발 프로젝트입니다.

## 현재 상태

- 기존 Anttitude M1~M5 평가와 분리된 신규 엔진
- 시간 제약형 source claim 계약
- factor catalog 및 turn causal graph 계약
- Graph Compiler와 구조 검증 fixture 구현
- 검증 전까지 `SHADOW_ONLY`

현재 구현은 실제 시장 인과효과를 발견하거나 수익률을 예측하지 않습니다. 전문가가 시점별로 검수한 기준 설명 그래프에 사용자 답안을 정렬하는 평가기를 목표로 합니다.

## 구조

```text
docs/specs/                    정책·스키마·M6·연구 근거
schemas/                       JSON Schema 계약
src/causal_engine/             Graph Compiler 패키지
src/compile_causal_graph.py    직접 실행용 CLI
examples/semiconductor_turn2/  구조 검증용 fixture
tests/                         회귀 테스트
```

## 테스트

```powershell
python -m unittest discover -s tests -v
```

## 그래프 컴파일

```powershell
python src/compile_causal_graph.py `
  --catalog examples/semiconductor_turn2/factor_catalog.json `
  --claims examples/semiconductor_turn2/source_claims.json `
  --graph examples/semiconductor_turn2/graph.json `
  --output outputs/semiconductor_turn2.compiled.json
```

상세 내용은 [빠른 시작 문서](docs/causal_engine_quickstart.md)를 참고하세요.

## 다음 단계

1. 사용자 답안 `Evidence`·`RelationEvidence` 입력 계약 구현
2. deterministic Graph Matcher 구현
3. M6 shadow scorer 구현
4. 사람 라벨 데이터 구축
5. 다중과제 요인·관계 추출기 학습
