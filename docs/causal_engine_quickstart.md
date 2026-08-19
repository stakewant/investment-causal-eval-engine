# Causal engine 빠른 시작

## 1. 테스트

```powershell
cd C:\dev\PycharmProjects\investment-causal-eval-engine
$env:PYTHONPATH="$PWD\src"
python -m unittest discover -s tests -v
```

## 2. 불변 평가 번들 생성

```powershell
python -m causal_engine.app_cli build-bundle `
  --catalog examples/semiconductor_turn2/factor_catalog.json `
  --claims examples/semiconductor_turn2/source_claims.json `
  --graph examples/semiconductor_turn2/graph.json `
  --output outputs/semiconductor_turn2.bundle.json
```

Graph Compiler가 시간 누수, 필수 근거, 끊어진 경로, 잘못된 역할, 의미 구간 수와 저자 검수 상태를 확인합니다. 그 뒤 catalog·claim·compiled graph 전체와 구성 버전을 해시로 묶습니다. 구성요소를 하나라도 변경하면 bundle ID가 바뀝니다.

## 3. 답안 평가

```powershell
python -m causal_engine.app_cli evaluate `
  --bundle outputs/semiconductor_turn2.bundle.json `
  --input examples/semiconductor_turn2/decision_complete.json `
  --output outputs/complete.result.json
```

비교 입력:

- `decision_complete.json`: 사건→산업→종목 노출→결과 연결
- `decision_partial.json`: 사건·산업은 인식했지만 종목 노출 누락
- `decision_list_only.json`: 요인을 나열했지만 관계를 설명하지 않음

## 4. 회귀 실험

```powershell
python -m causal_engine.app_cli run-experiment `
  --manifest examples/semiconductor_turn2/experiment.json
```

실험 명세는 입력별 기대 상태와 점수 범위를 고정합니다. 코드나 정책 변경 후 `COMPLETE`, `PARTIAL`, `DISCONNECTED` 경계가 의도 없이 바뀌면 실패합니다.

## 5. 사람 주석 데이터

```powershell
python -m causal_engine.app_cli validate-annotations `
  --input examples/annotations_seed.jsonl
```

Validator는 원문 span, 관계 endpoint, M6 범위와 사용자·시나리오 단위 split leakage를 검사합니다. 실제 학습 전 [사람 주석 지침](ANNOTATION_GUIDE.md)과 [실험 프로토콜](EXPERIMENT_PROTOCOL.md)을 적용합니다.
