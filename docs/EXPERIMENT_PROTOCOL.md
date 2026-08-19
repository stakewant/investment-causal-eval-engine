# 논문 실험 프로토콜

## 연구 질문

1. 사용자 답안에서 금융 요인 span과 scope를 정확히 찾는가.
2. 관련 용어 나열과 명시적 인과관계를 구분하는가.
3. 산업 판단은 맞지만 선택 종목 노출이 틀린 부분 이해를 구분하는가.
4. M6가 사람 평가와 일치하면서 기존 M1~M5 오류를 중복 감점하지 않는가.
5. 턴 이후 정보와 사후 결과가 과정 평가에 들어가지 않는가.

## 데이터 분할

문장 무작위 분할을 금지한다. 동일 사용자의 문체와 동일 시나리오의 factor 표현이 누출되지 않도록 `(user_id, scenario_id)`를 하나의 group으로 묶는다. test set은 모델·별칭·임계값 확정 전에 고정하고 bundle ID와 함께 기록한다.

권장 데이터 게이트:

| 단계 | 최소 검수 데이터 |
|---|---:|
| span/scope 파일럿 | 문장 300개, 주요 라벨 양성 30개 |
| 서비스 후보 추출 | 문장 1,000개, 주요 라벨 양성 100개 |
| 관계 추출 파일럿 | 증거 쌍 500개, 주요 관계 양성 50개 |
| 경로 랭커 | 여러 시나리오의 검수 경로 1,000개 |

수치는 모델 성능 보장이 아니라 학습 실험을 시작할 최소 게이트다.

## 비교군과 ablation

- A: keyword/alias only
- B: learned factor/scope candidate + Validator
- C: B + relation extractor
- D: C + semantic-segment Graph Matcher
- E: D + 사람 평가로 학습한 score calibrator
- F: LLM 구조화 후보 + 동일 Validator와 정책 scorer

각 단계는 같은 고정 test set에서 비교한다. calibrator가 좋아 보여도 test set으로 학습하지 않는다. LLM 단독 점수와 자체 scorer를 별도 비교해 재현성과 calibration 차이를 보고한다.

## 지표

| 대상 | 지표 |
|---|---|
| 요인 span | exact span Precision/Recall/F1, overlap F1 |
| factor/scope/direction | label Macro-F1, confusion matrix |
| 관계 | relation Macro-F1, cause/effect evidence F1 |
| 경로 | segment match F1, path status accuracy |
| M6 | QWK, MAE, RMSE, bootstrap 95% CI |
| 사람 합의 | pairwise QWK, exact agreement, ICC(A,1) |
| 신뢰도 | ECE, reliability plot |
| 시간 안전성 | temporal leakage 실패 수, 목표 0건 |
| 피드백 | 근거 없는 claim 비율, 사람 선호율 |

주요 결과에는 point estimate만 쓰지 않고 사용자·시나리오 group bootstrap 신뢰구간을 보고한다.

## 오류 분석 층

- alias 미등록 또는 한국어 형태 변화
- scope 혼동
- 부정·조건·방향 오류
- 문장 간 관계 누락
- 산업→종목 연결 약화
- 대체 경로지만 기준 그래프에 없음
- 미래정보 또는 사후 결과 누수
- M1~M5 오류 중복 소유

오류 분석으로 발견한 새 factor와 경로는 기존 test 결과를 덮어쓰지 않는다. 다음 catalog/graph/bundle version에 추가하고 이전 결과도 보존한다.

## 승격 기준

초기 기준은 factor Macro-F1 0.80, scope Macro-F1 0.85, 주요 관계 F1 0.75, M6 QWK 0.70, 미래정보 누수 0건, 피드백 사람 선호율 70% 이상이다. 모든 기준을 충족해도 `SHADOW → INTERNAL_REVIEW → FEEDBACK_ONLY → SCORE_PREVIEW → PRIMARY` 순서를 거친다.

## 재현 명령

```powershell
causal-engine run-experiment `
  --manifest examples/semiconductor_turn2/experiment.json

causal-engine metrics `
  --input outputs/m6_gold_predictions.jsonl `
  --type ordinal
```

실험 보고서에는 git commit, evaluator bundle ID, dataset version, split manifest, random seed와 실행 명령을 기록한다.
