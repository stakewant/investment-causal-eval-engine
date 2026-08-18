# 평가 엔진 연구 근거 및 관련 연구 v1

- 문서 ID: `RESEARCH_FOUNDATIONS_V1`
- 상태: 논문·설계 문서 공통 인용 기준안
- 적용 대상: 시간 제약형 출처 정책, 인과 요인 그래프, M6 shadow 평가, 학위논문 관련 연구

## 1. 연구 범위와 주장 경계

본 프로젝트의 신규 엔진은 역사적 금융 사건의 실제 인과효과를 관측 데이터만으로 식별하는 `causal discovery` 또는 수익률 예측 모델이 아니다.

본 프로젝트가 구현하려는 것은 다음 세 요소의 결합이다.

1. 전문가가 당시 이용 가능했던 자료와 사후 검수 자료를 분리해 시점별 기준 설명 그래프를 구축한다.
2. 학습형 NLP 모델이 사용자 답안에서 요인 span, 대상 종목, 방향과 관계 후보를 추출한다.
3. 자체 Validator와 Graph Matcher가 기준 그래프에 대한 경로 이해를 판정하고, 검증된 정책으로 shadow 점수와 피드백 계획을 만든다.

따라서 논문에서는 `인과 발견`보다 `시간 제약형 인과경로 이해 평가`, `설명 그래프 정렬`, `금융 의사결정 근거 평가`라는 표현을 사용한다. 그래프 신경망을 적용하더라도 그 출력은 대체 경로 후보 또는 정렬 점수이며, 경제적 인과효과의 식별값으로 주장하지 않는다.

## 2. 연구 축별 핵심 근거

### 2.1 결과가 아니라 당시 판단 과정을 평가

Fischhoff는 결과를 알고 나면 과거 사건이 실제보다 예측 가능했던 것처럼 재구성되는 hindsight bias를 보였고, Baron과 Hershey는 같은 의사결정 정보가 주어져도 좋은 결과가 나온 결정을 더 높은 품질로 평가하는 outcome bias를 실험했다. 이는 이후 수익률과 실제 결말을 M1~M6에서 분리하고, `information_cutoff_at` 당시의 정보로 판단 과정을 평가해야 하는 직접 근거다.

관련 설계:

- `AS_OF_EVIDENCE`, `RETROSPECTIVE_ANALYSIS`, `OUTCOME_EVIDENCE` 분리
- 진행 중 턴에서 미래 가격·결말·사후 분석 차단
- 결과 수익률과 판단 과정 점수의 분리

핵심 문헌: [R1], [R2]

### 2.2 뉴스는 사건의 진실 그 자체가 아니라 시점별 정보 채널

Engelberg와 Parsons는 같은 정보 사건이라도 지역 언론 노출과 보도 시점이 거래 행동에 영향을 줄 수 있음을 분석했다. Tetlock은 새로운 내용과 이전 보도의 반복을 구분하지 못할 때 stale news에 대한 과잉반응과 이후 반전이 나타날 수 있음을 보고했다. 따라서 뉴스는 중요하지만, 모든 뉴스를 독립적인 새 사건 또는 정답으로 취급해서는 안 된다.

관련 설계:

- `published_at`, `available_at`, `visible_at` 분리
- 같은 문서 안의 claim별 시점·역할 판정
- 뉴스 신선도·중복도·출처 다양성을 별도 메타데이터로 관리
- 뉴스 외 공시·시장 데이터·산업 구조 근거와 교차검증

핵심 문헌: [R3], [R4]

### 2.3 자유서술 답안의 자동평가

Student Response Analysis와 Automatic Short Answer Grading 연구는 학생 답안을 단순 키워드 일치가 아니라 정답·오답·부분 이해와 의미 관계로 분류하는 문제로 다룬다. SemEval-2013 Task 7은 교육 답안의 의미 추론 벤치마크를 제시했고, Burrows 등은 ASAG의 접근법과 평가 경향을 정리했다. Li 등은 질문·루브릭·답안 사이의 관계 표현을 학습했고, ExASAG는 예측과 함께 사람 근거에 대응하는 설명 구간을 평가했다.

관련 설계:

- 답안 span을 원문에 고정한 `Evidence`
- 질문·턴 학습목표·기준 그래프와 답안의 공동 입력
- 부분 이해, 잘못된 방향, 누락과 `NOT_ASSESSED` 구분
- 정확도뿐 아니라 근거 span과 사람 평가 일치도 측정

핵심 문헌: [R5], [R6], [R7], [R8]

### 2.4 주장 구조와 설명 그래프

Stab과 Gurevych는 텍스트에서 주장 구성요소와 관계를 공동 식별하는 argument mining 구조를 제안했다. ExplaGraphs는 정답만 맞히는 대신 연결되고 완전하며 모호하지 않은 설명 그래프를 생성·검증하는 문제를 제시했다. Marro 등은 텍스트 특성과 argument graph의 관계 구조를 함께 사용해 논증 품질을 평가했다.

관련 설계:

- 요인 노드와 `RelationEvidence`를 별도로 저장
- 노드 나열과 실제 인과 연결을 구분
- 필수 의미 구간, 연결성, 방향과 대체 경로 검증
- Graph Compiler를 통한 구조·시간·출처 사전 검증

핵심 문헌: [R9], [R10], [R13]

### 2.5 금융 문서의 인과관계 추출

FinCausal은 금융 문서에서 원인과 결과를 탐지하고 관계를 추출하는 공유 과제를 제공했다. Sakaji와 Izumi는 금융 인과 표현과 의존구조를 이용한 추출을 다뤘다. 일반 정보추출 분야의 DyGIE++는 span 기반 다중과제 구조로 entity, relation과 event를 함께 처리하며 문장 간 문맥을 활용했다.

관련 설계:

- 요인 span·entity·방향·관계의 다중과제 추출
- 문장 내부 관계에서 인접 문장 관계로 단계적 확장
- 금융 clue expression과 학습형 후보의 결합
- 모델 출력 뒤 자체 시간·출처·entity Validator 적용

핵심 문헌: [R11], [R12], [R16]

### 2.6 임베딩 검색과 LLM의 제한된 역할

Sentence-BERT는 문장 임베딩을 이용한 효율적인 의미 유사도 검색의 기초를 제공하며, KURE는 한국어 검색용 구현 후보로 사용할 수 있다. 다만 KURE 저장소만으로 학술 근거를 대신하지 않고 기반 문장 임베딩 연구와 함께 인용한다.

LLM-Rubric은 다차원 루브릭과 사람 평가에 대한 calibration의 필요성을 보였다. 본 프로젝트는 이를 더 보수적으로 적용해 LLM을 구조화 후보와 최종 문장 렌더링에 사용하고, 점수·경로·정보 시점의 확정은 자체 엔진이 담당한다.

핵심 문헌: [R14], [R15], [R17]

## 3. 현재 제출 논문과의 차이

현재 제출본 참고문헌에는 시뮬레이션 교육, 형성평가, 루브릭 타당도, LLM-Rubric, 금융 사건 지식그래프, 금융 인과추출, KURE가 이미 포함되어 있다.

### 우선 추가 권장 8편

1. [R1] Fischhoff — 미래 결과 차단과 hindsight bias
2. [R2] Baron & Hershey — 수익률과 판단 품질 분리
3. [R3] Engelberg & Parsons — 실제 정보 노출과 보도 시점
4. [R5] Dzikovska et al. — 학생 자유서술 의미평가
5. [R6] Burrows et al. — ASAG 연구 체계
6. [R9] Stab & Gurevych — 답안 구성요소와 관계 추출
7. [R12] FinCausal — 금융 원인·결과 관계 추출
8. [R13] Marro et al. — 텍스트와 그래프를 결합한 논증 품질 평가

### 방법론 상세화 때 추가할 문헌

- span 기반 다중과제 추출기를 구현할 때 [R11]
- 질문·루브릭·답안 관계망을 비교할 때 [R7]
- 설명 가능성 평가를 넣을 때 [R8]
- 그래프 구조 제약과 대체 경로 연구를 설명할 때 [R10]
- KURE 기반 후보 검색을 설명할 때 [R14]
- 뉴스 중복·신선도 특성을 넣을 때 [R4]

## 4. 논문 본문에 넣을 수 있는 관련 연구 서술 초안

### 4.1 판단 시점과 결과편향

> 역사적 투자판단을 사후 수익률만으로 평가하면 결과지식이 당시 사건의 예측 가능성과 의사결정 품질 평가를 왜곡할 수 있다. Fischhoff [R1]는 결과지식에 따른 hindsight bias를, Baron과 Hershey [R2]는 동일한 의사결정 과정도 결과에 따라 다르게 평가되는 outcome bias를 보고하였다. 이에 본 연구는 판단 과정 평가와 포트폴리오 결과를 분리하고, 각 턴의 정보 마감시각 이전에 이용 가능했던 근거만을 과정 채점에 사용한다.

### 4.2 자유서술 평가와 인과관계 추출

> 자유서술형 학습자 답안의 평가는 키워드 검출보다 의미적 부분정답과 관계 이해를 판별해야 한다. Student Response Analysis [R5]와 ASAG 연구 [R6], [R7]는 질문·기준답안·학습자 답안 사이의 의미 관계를 학습하는 기반을 제공한다. 본 연구는 금융 답안의 요인 span과 종목 대상을 추출한 뒤, 별도의 관계 증거를 기준 인과 그래프에 정렬함으로써 요인 나열과 실제 전달경로 설명을 구분한다.

### 4.3 설명 그래프 기반 M6

> Argument mining은 텍스트의 주장 구성요소와 관계 구조를 함께 복원하며 [R9], 그래프 기반 논증평가는 텍스트 표현과 관계 구조를 결합할 수 있음을 보였다 [R13]. 금융 분야에서도 FinCausal [R12]과 금융 인과표현 연구 [R16]가 원인·결과 추출 문제를 다루었다. 이를 바탕으로 본 연구의 M6는 시장·산업 요인이 개별 종목의 노출과 결과로 연결되는 의미 구간을 평가한다. 다만 이 그래프는 경제적 인과효과를 새로 식별하는 도구가 아니라, 시점별로 검수된 기준 설명구조에 대한 학습자 답안의 이해도를 평가하는 도구다.

### 4.4 LLM과 자체 엔진의 역할 분리

> LLM 기반 자동평가는 다차원 루브릭과 사람 평가에 대한 calibration이 필요하다 [R15]. 본 연구에서는 LLM이 답안의 구조화 후보와 피드백 문장 생성을 담당하지만, 원문 span 검증, 정보 시점 검증, 그래프 정렬과 점수 계산은 버전이 고정된 자체 평가기가 수행한다. 이를 통해 생성모델의 유연성을 사용하면서도 점수 재현성과 미래정보 차단을 유지한다.

## 5. 연구 평가에 연결할 지표

| 연구 질문 | 정량 지표 | 근거 문헌 |
|---|---|---|
| 요인 span을 정확히 찾는가 | span Precision, Recall, F1 | [R8], [R11] |
| 원인·결과 관계를 찾는가 | relation Macro-F1, evidence F1 | [R11], [R12], [R16] |
| 부분 이해를 구분하는가 | label Macro-F1, QWK | [R5], [R6], [R7] |
| 그래프 품질을 평가하는가 | segment match F1, path accuracy, QWK | [R10], [R13] |
| 사람 채점과 일치하는가 | QWK, MAE, ICC, bootstrap CI | [R6], [R15] |
| 미래정보를 차단하는가 | temporal leakage test failure count | [R1], [R2] |
| 설명이 근거에 충실한가 | rationale overlap, unsupported-claim rate | [R8] |

## 6. 참고문헌

- **[R1]** B. Fischhoff, “Hindsight ≠ Foresight: The Effect of Outcome Knowledge on Judgment Under Uncertainty,” *Journal of Experimental Psychology: Human Perception and Performance*, vol. 1, no. 3, pp. 288–299, 1975. [doi:10.1037/0096-1523.1.3.288](https://doi.org/10.1037/0096-1523.1.3.288)
- **[R2]** J. Baron and J. C. Hershey, “Outcome Bias in Decision Evaluation,” *Journal of Personality and Social Psychology*, vol. 54, no. 4, pp. 569–579, 1988. [doi:10.1037/0022-3514.54.4.569](https://doi.org/10.1037/0022-3514.54.4.569)
- **[R3]** J. E. Engelberg and C. A. Parsons, “The Causal Impact of Media in Financial Markets,” *The Journal of Finance*, vol. 66, no. 1, pp. 67–97, 2011. [doi:10.1111/j.1540-6261.2010.01626.x](https://doi.org/10.1111/j.1540-6261.2010.01626.x)
- **[R4]** P. C. Tetlock, “All the News That’s Fit to Reprint: Do Investors React to Stale Information?,” *The Review of Financial Studies*, vol. 24, no. 5, pp. 1481–1512, 2011. [doi:10.1093/rfs/hhq141](https://doi.org/10.1093/rfs/hhq141)
- **[R5]** M. Dzikovska et al., “SemEval-2013 Task 7: The Joint Student Response Analysis and 8th Recognizing Textual Entailment Challenge,” in *SemEval 2013*, pp. 263–274, 2013. [ACL Anthology](https://aclanthology.org/S13-2045/)
- **[R6]** S. Burrows, I. Gurevych, and B. Stein, “The Eras and Trends of Automatic Short Answer Grading,” *International Journal of Artificial Intelligence in Education*, vol. 25, pp. 60–117, 2015. [doi:10.1007/s40593-014-0026-8](https://doi.org/10.1007/s40593-014-0026-8)
- **[R7]** Z. Li, Y. Tomar, and R. J. Passonneau, “A Semantic Feature-Wise Transformation Relation Network for Automatic Short Answer Grading,” in *EMNLP 2021*, pp. 6030–6040, 2021. [doi:10.18653/v1/2021.emnlp-main.487](https://doi.org/10.18653/v1/2021.emnlp-main.487)
- **[R8]** M. Tornqvist, M. Mahamud, E. Mendez Guzman, and A. Farazouli, “ExASAG: Explainable Framework for Automatic Short Answer Grading,” in *BEA 2023*, pp. 361–371, 2023. [doi:10.18653/v1/2023.bea-1.29](https://doi.org/10.18653/v1/2023.bea-1.29)
- **[R9]** C. Stab and I. Gurevych, “Parsing Argumentation Structures in Persuasive Essays,” *Computational Linguistics*, vol. 43, no. 3, pp. 619–659, 2017. [doi:10.1162/COLI_a_00295](https://doi.org/10.1162/COLI_a_00295)
- **[R10]** S. Saha, P. Yadav, L. Bauer, and M. Bansal, “ExplaGraphs: An Explanation Graph Generation Task for Structured Commonsense Reasoning,” in *EMNLP 2021*, pp. 7716–7740, 2021. [doi:10.18653/v1/2021.emnlp-main.609](https://doi.org/10.18653/v1/2021.emnlp-main.609)
- **[R11]** D. Wadden, U. Wennberg, Y. Luan, and H. Hajishirzi, “Entity, Relation, and Event Extraction with Contextualized Span Representations,” in *EMNLP-IJCNLP 2019*, pp. 5784–5789, 2019. [doi:10.18653/v1/D19-1585](https://doi.org/10.18653/v1/D19-1585)
- **[R12]** D. Mariko, H. Abi-Akl, K. Trottier, and M. El-Haj, “The Financial Causality Extraction Shared Task (FinCausal 2022),” in *FNP 2022*, pp. 105–107, 2022. [ACL Anthology](https://aclanthology.org/2022.fnp-1.16/)
- **[R13]** S. Marro, E. Cabrio, and S. Villata, “Graph Embeddings for Argumentation Quality Assessment,” in *Findings of EMNLP 2022*, pp. 4154–4164, 2022. [doi:10.18653/v1/2022.findings-emnlp.306](https://doi.org/10.18653/v1/2022.findings-emnlp.306)
- **[R14]** N. Reimers and I. Gurevych, “Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks,” in *EMNLP-IJCNLP 2019*, pp. 3982–3992, 2019. [doi:10.18653/v1/D19-1410](https://doi.org/10.18653/v1/D19-1410)
- **[R15]** H. Hashemi, J. Eisner, C. Rosset, B. Van Durme, and C. Kedzie, “LLM-Rubric: A Multidimensional, Calibrated Approach to Automated Evaluation of Natural Language Texts,” in *ACL 2024*, pp. 13806–13834, 2024. [doi:10.18653/v1/2024.acl-long.745](https://doi.org/10.18653/v1/2024.acl-long.745)
- **[R16]** H. Sakaji and K. Izumi, “Financial Causality Extraction Based on Universal Dependencies and Clue Expressions,” *New Generation Computing*, vol. 41, no. 4, pp. 839–857, 2023. [doi:10.1007/s00354-023-00233-2](https://doi.org/10.1007/s00354-023-00233-2)
- **[R17]** N. Kim, S. Kim, J. Won, and S. Lee, “KURE: Korea University Retrieval Embedding Model,” Korea University NLP & AI Lab, 2024. [GitHub repository](https://github.com/nlpai-lab/KURE)

## 7. 관련 설계 문서

- [시간 제약형 출처 정책 v1](./TEMPORAL_SOURCE_POLICY_V1.md)
- [인과 요인 그래프 스키마 v1](./CAUSAL_FACTOR_GRAPH_SCHEMA_V1.md)
- [M6 영향 경로·대상 연결 채점 정책 v1](./M6_SCORING_POLICY_V1.md)




