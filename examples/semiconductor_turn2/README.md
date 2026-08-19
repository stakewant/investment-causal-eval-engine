# Semiconductor turn 2 compiler fixture

이 디렉터리는 Graph Compiler의 정상 동작을 검증하기 위한 구조 fixture다.

- 실제 시나리오에 사용할 역사적 출처가 아니다.
- `source_type=FIXTURE`인 claim을 운영 데이터로 승격해서는 안 된다.
- 실제 시나리오 전환 시 출처 URL, 원문 span, 공개시각과 사람 검수를 교체해야 한다.

실행:

```powershell
python src/compile_causal_graph.py `
  --catalog examples/semiconductor_turn2/factor_catalog.json `
  --claims examples/semiconductor_turn2/source_claims.json `
  --graph examples/semiconductor_turn2/graph.json `
  --output outputs/semiconductor_turn2.compiled.json
```

독립 평가 실행:

```powershell
causal-engine build-bundle `
  --catalog examples/semiconductor_turn2/factor_catalog.json `
  --claims examples/semiconductor_turn2/source_claims.json `
  --graph examples/semiconductor_turn2/graph.json `
  --output outputs/semiconductor_turn2.bundle.json

causal-engine evaluate `
  --bundle outputs/semiconductor_turn2.bundle.json `
  --input examples/semiconductor_turn2/decision_complete.json `
  --output outputs/semiconductor_turn2.complete.result.json
```

`decision_partial.json`은 종목 노출 누락, `decision_list_only.json`은 관계 없는 요인 나열 회귀 테스트용이다.

