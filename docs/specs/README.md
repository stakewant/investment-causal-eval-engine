# Causal Engine v2 specifications

이 디렉터리는 독립 평가엔진의 설계 source of truth다.

- [시간 제약형 출처 정책](./TEMPORAL_SOURCE_POLICY_V1.md)
- [인과 요인 그래프 스키마](./CAUSAL_FACTOR_GRAPH_SCHEMA_V1.md)
- [M6 shadow 채점 정책](./M6_SCORING_POLICY_V1.md)
- [연구 근거 및 관련 연구](./RESEARCH_FOUNDATIONS_V1.md)

통합 시나리오 서버에는 안정화된 bundle과 API 계약만 전달한다. 정책·그래프 스키마·채점 기준의 원본은 이 프로젝트에서 버전 관리한다.

실행 구현과 논문 실험 문서는 상위 `docs/`의 아키텍처, 사람 주석 지침, 실험 프로토콜과 모델 카드를 따른다. 명세와 코드가 충돌하면 명세 버전을 올리고 회귀 실험을 갱신한 뒤 새 evaluator bundle을 발행한다.

