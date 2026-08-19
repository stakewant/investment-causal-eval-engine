# Investment Causal Evaluation Engine

투자 시나리오의 자유서술 근거를 시점별 기준 인과 그래프에 정렬하고, 시장·산업 요인이 선택 종목의 실제 노출과 결과로 이어지는 경로 이해를 M6로 평가하는 독립 연구 엔진입니다.

현재 버전은 통합 서버와 분리된 `SHADOW` 전용 종단 실행 기준선입니다. 기존 Anttitude M1~M5 점수, 총점, 등급과 마이페이지 기록을 변경하지 않습니다.

## 구현 범위

- claim 단위 시간·공개·노출·채점 정책과 미래정보 차단
- factor catalog, turn graph와 author review gate
- 순환·단절·출처·시간·복잡도를 검사하는 Graph Compiler
- 해시로 고정되는 portable evaluator bundle
- 한국어 별칭 기반 요인 span 추출과 외부 신경망·LLM 후보 입력 게이트
- 원문 span, factor, scope, entity, 방향과 신뢰도 검증
- 명시적 `RelationEvidence` 추출과 관계 없는 요인 나열 구분
- 필수 의미 구간 기반 Graph Matcher와 직접·간접·대체 경로 처리
- 종목별·턴별 M6, 중복감점 방지, cap과 노출 진단
- 시점에 안전한 `FeedbackPlan`, 출력 검증과 한국어 템플릿 피드백
- 기준에 없는 경로의 무점수 사람 검토 큐
- annotation 검증, 사용자·시나리오 단위 split leakage 검사
- 학습 가능한 해시 softmax 후보 분류기와 연구용 feed-forward score calibrator
- Macro-F1, span F1, QWK, MAE, RMSE, ICC와 bootstrap CI
- 독립 회귀 실험 manifest와 29개 이상의 단위·종단 테스트

이 프로젝트는 역사적 시장의 실제 인과효과를 새로 식별하는 causal discovery 모델이나 수익률 예측기가 아닙니다. 당시 정보로 검수된 기준 설명 그래프에 사용자의 경로 이해를 정렬하는 평가기입니다.

## 빠른 실행

Python 3.11 이상에서 외부 런타임 의존성 없이 실행됩니다.

```powershell
cd C:\dev\PycharmProjects\investment-causal-eval-engine
python -m pip install -e .

causal-engine build-bundle `
  --catalog examples/semiconductor_turn2/factor_catalog.json `
  --claims examples/semiconductor_turn2/source_claims.json `
  --graph examples/semiconductor_turn2/graph.json `
  --output outputs/semiconductor_turn2.bundle.json

causal-engine evaluate `
  --bundle outputs/semiconductor_turn2.bundle.json `
  --input examples/semiconductor_turn2/decision_complete.json `
  --output outputs/semiconductor_turn2.complete.result.json

causal-engine run-experiment `
  --manifest examples/semiconductor_turn2/experiment.json `
  --output outputs/semiconductor_turn2.experiment.json

python -m unittest discover -s tests -v
```

편집 설치 없이 실행하려면 PowerShell에서 `$env:PYTHONPATH="$PWD\src"`를 먼저 지정하면 됩니다.

## 연구 데이터와 학습 기준선

```powershell
causal-engine validate-annotations `
  --input examples/annotations_seed.jsonl

causal-engine export-training `
  --input examples/annotations_seed.jsonl `
  --output outputs/training_rows.jsonl

causal-engine train-classifier `
  --input outputs/training_rows.jsonl `
  --task DIRECTION `
  --model outputs/direction.model.json
```

기본 분류기는 데이터·평가 파이프라인 검증용 학습 기준선입니다. 운영 M6 점수 권한을 갖지 않으며, 향후 한국어 사전학습 모델이나 다중과제 신경망도 동일한 후보 계약과 Validator를 통과해야 합니다.

## 디렉터리

```text
docs/specs/                    정책·그래프·M6·연구 근거 source of truth
docs/                          아키텍처·주석·실험·모델 카드
schemas/                       입력·증거·그래프·결과 JSON Schema
src/causal_engine/             컴파일·추출·매칭·채점·피드백·연구 도구
examples/semiconductor_turn2/  종단 실행과 회귀 실험 fixture
tests/                         정책 경계와 결정론 회귀 테스트
outputs/                       생성물; Git 추적 제외
```

## 문서

- [아키텍처와 신뢰 경계](docs/ARCHITECTURE.md)
- [사람 주석 지침](docs/ANNOTATION_GUIDE.md)
- [논문 실험 프로토콜](docs/EXPERIMENT_PROTOCOL.md)
- [학습 기준선 모델 카드](docs/MODEL_CARD_BASELINE.md)
- [빠른 시작](docs/causal_engine_quickstart.md)
- [설계 명세](docs/specs/README.md)

## 다음 연구 단계

코드가 없는 것이 아니라 데이터가 필요한 단계가 남아 있습니다. 검수 문장을 수집해 사람 합의를 측정하고, 해시 기준선·한국어 encoder·관계 추출기·그래프 랭커를 같은 고정 test set에서 비교해야 합니다. 통합 서버 연동과 사용자 화면 공개는 이 저장소의 shadow 검증과 승격 기준을 통과한 뒤 별도 작업으로 진행합니다.
