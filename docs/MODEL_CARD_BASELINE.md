# 학습 기준선 모델 카드

## 모델

`HashedSoftmaxClassifier`는 한국어 단어와 2~4자 character n-gram을 고정 차원에 해시하고, softmax 회귀를 SGD로 학습하는 작은 기준선이다. factor, scope, direction, relation 과제를 각각 학습할 수 있다.

`RubricCalibrator`는 구성요소 점수·신뢰도 같은 고정 수치 특징을 사람 M6에 맞추는 작은 1-hidden-layer feed-forward network다. LLM-Rubric에서 제기한 다차원 평가와 사람 보정 문제를 실험하기 위한 연구 도구다.

## 허용된 사용

- annotation/export/training 파이프라인 검증
- 규칙 기준선과 한국어 encoder의 비교
- confidence와 calibration 실험
- 외부 모델 후보가 Validator를 통과하는지 종단 실험

## 금지된 사용

- 학습 데이터가 거의 없는 상태에서 운영 점수 권한 부여
- model confidence만으로 `SCORE_ELIGIBLE` 승인
- 시간 정책·기준 graph·cap 변경
- 사람 합의와 고정 test set 없이 PRIMARY 승격

## 알려진 한계

- 문맥화 encoder가 아니므로 장거리 관계와 동음 표현에 약하다.
- span 탐색 자체는 catalog 별칭 또는 외부 후보에 의존한다.
- 소규모 class imbalance에서 확률이 과신될 수 있다.
- 금융 사건의 실제 인과효과나 주가를 예측하지 않는다.

## 향후 모델 비교

한국어 사전학습 encoder의 다중과제 span/scope/direction/entity head, 금융 관계 추출 head와 graph path ranker를 순차 비교한다. 어떤 모델도 `EvidenceValidator`, `RelationValidator`, `TemporalPolicy`, `GraphMatcher`와 고정 M6 정책을 우회하지 않는다.
