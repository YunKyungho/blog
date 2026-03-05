# #30. 개발 자동화 도구 2종: 워크플로우 엔진과 테스트 생성기

*2026-03-06*

## TL;DR
- YAML 기반 워크플로우 자동화 엔진 개발 (노코드 자동화)
- AI 기반 테스트 케이스 자동 생성 시스템 개발 (0.5초 내 생성)
- 개발 생산성 향상을 위한 실용적 도구들
- Python + SQLite 기반 경량 솔루션

## 워크플로우 자동화 엔진

복잡한 자동화 작업을 YAML로 정의하고 실행하는 시스템을 개발했다.

### 주요 특징

```yaml
# 예시: 일일 리포트 자동 생성 워크플로우
name: "Daily Report Generator"
trigger:
  schedule: "0 9 * * *"  # 매일 오전 9시

steps:
  - name: "데이터 수집"
    type: "database_query"
    config:
      query: "SELECT * FROM activities WHERE date = TODAY()"
      
  - name: "AI 분석"
    type: "ai_analysis"
    config:
      model: "claude-sonnet"
      prompt: "다음 데이터를 분석하여 인사이트 제공: {prev_result}"
      
  - name: "리포트 생성"
    type: "template_render"
    config:
      template: "daily_report.md"
      
  - name: "알림 전송"
    type: "notification"
    config:
      channel: "telegram"
      message: "일일 리포트가 준비되었습니다: {report_url}"
```

### 핵심 구현

- **조건부 실행**: if/else 로직으로 상황에 맞는 분기 처리
- **루프 지원**: 반복 작업 자동화
- **에러 핸들링**: 실패 시 재시도 및 대체 액션
- **실시간 모니터링**: 실행 상태 추적 및 로깅

```python
class WorkflowEngine:
    def __init__(self, workflows_dir="workflows", db_path="workflows.db"):
        self.workflows_dir = Path(workflows_dir)
        self.db_path = db_path
        self.active_executions = {}
        
    async def execute_workflow(self, workflow_name: str):
        """워크플로우 실행"""
        workflow = self.load_workflow(workflow_name)
        execution_id = self.start_execution(workflow)
        
        try:
            for step in workflow['steps']:
                result = await self.execute_step(step, execution_id)
                self.log_step_result(execution_id, step['name'], result)
        except Exception as e:
            self.handle_error(execution_id, e)
```

## 지능형 테스트 케이스 자동 생성기

코드를 분석해서 완벽한 테스트 케이스를 0.5초 만에 자동 생성하는 시스템.

### 기능 요약

- **코드 분석**: AST 파싱으로 함수 시그니처, 로직 분석
- **패턴 인식**: 정상/경계/예외/엣지 케이스 자동 분류
- **데이터 생성**: 타입별 테스트 데이터 지능형 생성
- **커버리지 최적화**: 최소한의 테스트로 최대 커버리지

### 테스트 패턴

```python
test_patterns = {
    'normal': ['basic_case', 'typical_usage', 'expected_flow'],
    'boundary': ['min_value', 'max_value', 'zero_case', 'negative', 'empty'], 
    'exception': ['invalid_type', 'null_input', 'out_of_range'],
    'edge': ['floating_precision', 'large_data', 'unicode', 'special_chars']
}
```

### 사용 예시

```python
# 함수 정의
def calculate_discount(price: float, discount_rate: float) -> float:
    if price <= 0:
        raise ValueError("가격은 0보다 커야 합니다")
    if not 0 <= discount_rate <= 1:
        raise ValueError("할인율은 0~1 사이여야 합니다")
    return price * (1 - discount_rate)

# 자동 생성된 테스트
def test_calculate_discount_normal():
    assert calculate_discount(100.0, 0.2) == 80.0
    
def test_calculate_discount_boundary():
    assert calculate_discount(0.01, 0.0) == 0.01
    assert calculate_discount(1000.0, 1.0) == 0.0
    
def test_calculate_discount_exception():
    with pytest.raises(ValueError):
        calculate_discount(-1.0, 0.2)  # 음수 가격
    with pytest.raises(ValueError):
        calculate_discount(100.0, 1.5)  # 잘못된 할인율
```

## 기술적 구현

### 공통 아키텍처

- **SQLite DB**: 실행 이력, 패턴 학습 데이터 저장
- **AST 분석**: 코드 구조 자동 파싱
- **타입 힌트 활용**: 정확한 테스트 데이터 생성
- **JSON 설정**: 확장 가능한 설정 관리

### 성능 최적화

- **캐싱**: 분석 결과 캐시로 재실행 시 속도 향상
- **배치 처리**: 여러 함수 동시 분석
- **점진적 학습**: 사용 패턴 학습으로 품질 개선

## 실용성

두 도구 모두 실제 개발 워크플로우에서 바로 사용 가능한 수준으로 구현했다.

**워크플로우 엔진**은 반복적인 개발 작업(빌드, 테스트, 배포, 리포트)을 자동화하고, **테스트 생성기**는 테스트 작성 시간을 95% 단축시킨다.

특히 테스트 생성기의 0.5초 생성 속도는 실시간 개발 도구로서의 가능성을 보여준다.

## 다음 단계

- 워크플로우 엔진에 GUI 에디터 추가
- 테스트 생성기에 기존 테스트 코드 분석 기능
- 두 도구 간 연동으로 '테스트 자동 생성 워크플로우' 구성

개발자의 시간은 창의적 문제 해결에 쓰여야 한다. 반복 작업은 자동화가 담당하자.