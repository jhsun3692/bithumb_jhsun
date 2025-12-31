# 빗썸 자동매매 AI 기능 구현 가이드

## 📋 목차
1. [개요](#개요)
2. [설치 및 설정](#설치-및-설정)
3. [단계 1: 파라미터 자동 최적화](#단계-1-파라미터-자동-최적화)
4. [단계 2: 이상 탐지 시스템](#단계-2-이상-탐지-시스템)
5. [API 엔드포인트](#api-엔드포인트)
6. [사용 예제](#사용-예제)
7. [모범 사례](#모범-사례)

---

## 개요

이 프로젝트에 다음 AI 기능들이 추가되었습니다:

### ✅ 단계 1 (1-2주 구현 가능)
1. **파라미터 자동 최적화** - Optuna를 활용한 베이지안 최적화
2. **이상 탐지 시스템** - 가격/거래량/성과 이상 탐지

### 🎯 주요 기능
- 전략별 파라미터 자동 튜닝
- 백테스팅 기반 성능 평가
- 실시간 가격/거래량 이상 감지
- 전략 성과 모니터링 및 경보

---

## 설치 및 설정

### 1. 의존성 설치

프로젝트에 필요한 AI 라이브러리가 `pyproject.toml`에 추가되었습니다:

```bash
# 패키지 설치
pip install -e .
```

추가된 라이브러리:
- `optuna>=3.6.0` - 베이지안 최적화
- `scikit-learn>=1.4.0` - 머신러닝 유틸리티
- `scipy>=1.12.0` - 통계 분석
- `numpy>=1.26.0` - 수치 연산

### 2. 서버 실행

```bash
# 개발 모드
uvicorn app.main:app --reload

# 프로덕션 모드
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

서버가 실행되면 다음 URL에서 API 문서를 확인할 수 있습니다:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 단계 1: 파라미터 자동 최적화

### 개념

파라미터 자동 최적화는 **Optuna**를 사용하여 각 전략의 최적 파라미터를 찾습니다.

#### 최적화 가능한 전략 및 파라미터:

1. **이동평균 (Moving Average)**
   - `short_period`: 단기 이동평균 기간 (3-15일)
   - `long_period`: 장기 이동평균 기간 (15-50일)
   - `profit_target`: 목표 수익률 (1-10%)
   - `stop_loss`: 손절 비율 (1-5%)

2. **RSI (Relative Strength Index)**
   - `period`: RSI 계산 기간 (7-28일)
   - `oversold`: 과매도 임계값 (20-40)
   - `overbought`: 과매수 임계값 (60-80)
   - `profit_target`, `stop_loss`

3. **볼린저 밴드 (Bollinger Bands)**
   - `period`: 이동평균 기간 (10-40일)
   - `std_dev`: 표준편차 배수 (1.5-3.0)
   - `profit_target`, `stop_loss`

4. **MACD**
   - `fast_period`: 빠른 EMA 기간 (8-16일)
   - `slow_period`: 느린 EMA 기간 (20-35일)
   - `signal_period`: 시그널 기간 (5-15일)
   - `profit_target`, `stop_loss`

5. **Stochastic**
   - `k_period`: %K 기간 (10-21일)
   - `d_period`: %D 기간 (2-5일)
   - `oversold`: 과매도 임계값 (15-30)
   - `overbought`: 과매수 임계값 (70-85)
   - `profit_target`, `stop_loss`

### 최적화 방법

#### 방법 1: API를 통한 최적화 (추천)

```bash
# 특정 전략 최적화
curl -X POST "http://localhost:8000/ai/optimize-parameters?strategy_id=1&n_trials=50&days_back=90" \
  -H "Authorization: Bearer YOUR_TOKEN"

# 최적화 후 자동 적용
curl -X POST "http://localhost:8000/ai/optimize-parameters-and-apply?strategy_id=1&n_trials=50" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### 방법 2: Python 코드로 직접 사용

```python
from app.services.parameter_optimizer import ParameterOptimizer
from app.services.bithumb_api import BithumbAPI

# API 인스턴스 생성
api = BithumbAPI(api_key="YOUR_KEY", api_secret="YOUR_SECRET")

# 최적화 실행
optimizer = ParameterOptimizer(api)
result = optimizer.optimize_strategy(
    strategy_type="moving_average",  # 또는 rsi, bollinger, macd, stochastic
    coin="BTC",
    n_trials=50,  # 시도 횟수 (많을수록 정확하지만 느림)
    initial_balance=1000000,  # 초기 자금 (백테스팅용)
    days_back=90  # 과거 데이터 기간
)

# 결과 확인
print(f"최적 파라미터: {result['best_params']}")
print(f"샤프 비율: {result['sharpe_ratio']:.4f}")
print(f"총 수익률: {result['performance']['total_return']:.2f}%")
print(f"승률: {result['performance']['win_rate']:.2f}%")
```

### 최적화 결과 해석

```json
{
  "best_params": {
    "short_period": 7,
    "long_period": 28,
    "profit_target": 5.2,
    "stop_loss": 2.8
  },
  "sharpe_ratio": 1.85,
  "performance": {
    "total_return": 23.45,
    "max_drawdown": 8.32,
    "win_rate": 62.5,
    "num_trades": 24
  }
}
```

- **sharpe_ratio**: 샤프 비율 (높을수록 좋음, 1.0 이상이면 양호)
- **total_return**: 총 수익률 (%)
- **max_drawdown**: 최대 낙폭 (%)
- **win_rate**: 승률 (%)
- **num_trades**: 거래 횟수

---

## 단계 2: 이상 탐지 시스템

### 개념

이상 탐지 시스템은 다음을 모니터링합니다:

1. **가격 이상 탐지**: Z-score 기반 급등/급락 감지
2. **거래량 이상 탐지**: 비정상적인 거래량 증가/감소
3. **전략 성과 이상 탐지**: 연속 손실, 낮은 승률, 큰 낙폭

### 사용 방법

#### 1. 가격/거래량 이상 탐지

```bash
# REST API 호출
curl -X GET "http://localhost:8000/ai/detect-anomalies/BTC" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Python 코드:**

```python
from app.services.anomaly_detector import AnomalyDetector
from app.services.bithumb_api import BithumbAPI

# API 및 탐지기 초기화
api = BithumbAPI(api_key="YOUR_KEY", api_secret="YOUR_SECRET")
detector = AnomalyDetector(api)

# 가격 이상 탐지
price_result = detector.detect_price_anomalies(
    coin="BTC",
    threshold=3.0,  # Z-score 임계값 (3.0 = 99.7% 신뢰구간)
    lookback_days=30
)

if price_result["is_anomaly"]:
    print(f"⚠️ 가격 이상 탐지!")
    print(f"현재 변화율: {price_result['current_change_pct']:.2f}%")
    print(f"Z-score: {price_result['current_z_score']:.2f}")
    print(f"심각도: {price_result['severity']}")
    print(f"권장사항: {price_result['recommendation']}")

# 거래량 이상 탐지
volume_result = detector.detect_volume_anomalies(
    coin="BTC",
    threshold=2.5,
    lookback_days=30
)

if volume_result["is_anomaly"]:
    print(f"⚠️ 거래량 이상 탐지!")
    print(f"현재 거래량: {volume_result['current_volume']:,.0f}")
    print(f"평균 대비 비율: {volume_result['volume_ratio']:.2f}x")
```

#### 2. 전략 성과 모니터링

```bash
# REST API 호출
curl -X GET "http://localhost:8000/ai/strategy-health/1?lookback_trades=20" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Python 코드:**

```python
# 최근 거래 데이터 (DB에서 가져옴)
trades = [
    {"type": "sell", "profit": 15000, "amount": 0.001, "price": 50000000},
    {"type": "sell", "profit": -8000, "amount": 0.001, "price": 49000000},
    # ... 더 많은 거래
]

# 성과 이상 탐지
performance_result = detector.detect_strategy_performance_anomalies(
    trades=trades,
    lookback_trades=20
)

if performance_result["is_anomaly"]:
    print(f"⚠️ 전략 성과 이상 탐지!")
    print(f"승률: {performance_result['win_rate']:.1f}%")
    print(f"연속 손실: {performance_result['consecutive_losses']}회")
    print(f"현재 낙폭: {performance_result['current_drawdown']:,.0f} KRW")
    print(f"권장사항: {performance_result['recommendation']}")
```

#### 3. 종합 이상 탐지

```python
# 모든 이상 탐지를 한 번에 실행
comprehensive_result = detector.comprehensive_anomaly_check(
    coin="BTC",
    trades=trades  # 옵션
)

print(f"전체 리스크 레벨: {comprehensive_result['overall_risk_level']}")
if comprehensive_result['should_pause_trading']:
    print("⛔ 거래 일시 중지 권장!")
```

---

## API 엔드포인트

### 파라미터 최적화 엔드포인트

#### 1. POST `/ai/optimize-parameters`
특정 전략의 파라미터 최적화

**쿼리 파라미터:**
- `strategy_id` (int): 전략 ID
- `n_trials` (int, 기본값=50): 최적화 시도 횟수
- `days_back` (int, 기본값=90): 과거 데이터 기간

**응답:**
```json
{
  "success": true,
  "strategy_id": 1,
  "strategy_name": "BTC MA Strategy",
  "optimization_result": {
    "best_params": {...},
    "sharpe_ratio": 1.85,
    "performance": {...}
  }
}
```

#### 2. POST `/ai/optimize-parameters-and-apply`
최적화 후 자동으로 전략에 적용

**쿼리 파라미터:** 위와 동일

**응답:**
```json
{
  "success": true,
  "message": "Parameters optimized and applied successfully",
  "new_parameters": {...}
}
```

### 이상 탐지 엔드포인트

#### 3. GET `/ai/detect-anomalies/{coin}`
가격 및 거래량 이상 탐지

**경로 파라미터:**
- `coin` (str): 코인 심볼 (예: BTC, ETH)

**응답:**
```json
{
  "success": true,
  "anomaly_detection": {
    "price_anomaly": {...},
    "volume_anomaly": {...},
    "overall_risk_level": "low",
    "should_pause_trading": false
  }
}
```

#### 4. GET `/ai/strategy-health/{strategy_id}`
전략 성과 건강도 체크

**경로 파라미터:**
- `strategy_id` (int): 전략 ID

**쿼리 파라미터:**
- `lookback_trades` (int, 기본값=20): 분석할 최근 거래 수

**응답:**
```json
{
  "success": true,
  "strategy_id": 1,
  "health_report": {
    "win_rate": 65.0,
    "consecutive_losses": 2,
    "is_anomaly": false,
    "severity": "low",
    "recommendation": "Strategy performance is acceptable."
  }
}
```

#### 5. GET `/ai/market-risk/{coin}`
시장 리스크 평가

**응답:**
```json
{
  "success": true,
  "coin": "BTC",
  "overall_risk_level": "low",
  "risk_factors": [],
  "recommendation": "Normal market conditions. Continue with strategy."
}
```

---

## 사용 예제

### 예제 1: 전략 생성 및 파라미터 최적화

```python
# 1. 새 전략 생성 (웹 UI 또는 API로)
# 2. 파라미터 최적화 실행

import requests

# 로그인하여 토큰 받기
response = requests.post("http://localhost:8000/auth/login", json={
    "username": "your_username",
    "password": "your_password"
})
token = response.json()["access_token"]

headers = {"Authorization": f"Bearer {token}"}

# 전략 최적화 및 적용
response = requests.post(
    "http://localhost:8000/ai/optimize-parameters-and-apply",
    params={"strategy_id": 1, "n_trials": 100, "days_back": 180},
    headers=headers
)

result = response.json()
print(f"최적화 완료! 새 파라미터: {result['new_parameters']}")
```

### 예제 2: 정기적인 이상 탐지 모니터링

```python
import schedule
import time

def check_anomalies():
    response = requests.get(
        "http://localhost:8000/ai/detect-anomalies/BTC",
        headers=headers
    )
    result = response.json()

    if result["anomaly_detection"]["should_pause_trading"]:
        print("⛔ 리스크 감지! 거래 일시 중지!")
        # 전략 비활성화 로직
    else:
        print("✅ 정상 운영 중")

# 매 10분마다 이상 탐지 실행
schedule.every(10).minutes.do(check_anomalies)

while True:
    schedule.run_pending()
    time.sleep(1)
```

### 예제 3: 전략 성과 자동 모니터링

```python
def monitor_strategy_health(strategy_id):
    response = requests.get(
        f"http://localhost:8000/ai/strategy-health/{strategy_id}",
        params={"lookback_trades": 30},
        headers=headers
    )

    health = response.json()["health_report"]

    if health["is_anomaly"]:
        print(f"⚠️ 전략 {strategy_id} 성과 저하!")
        print(f"승률: {health['win_rate']:.1f}%")
        print(f"연속 손실: {health['consecutive_losses']}회")

        # 심각도에 따라 조치
        if health["severity"] == "critical":
            print("전략 중지 및 재최적화 필요!")
            # 재최적화 실행
            requests.post(
                "http://localhost:8000/ai/optimize-parameters-and-apply",
                params={"strategy_id": strategy_id, "n_trials": 50},
                headers=headers
            )

# 매일 자정에 체크
schedule.every().day.at("00:00").do(monitor_strategy_health, strategy_id=1)
```

---

## 모범 사례

### 1. 파라미터 최적화

✅ **권장사항:**
- 최소 60-90일의 과거 데이터 사용
- n_trials는 30-100 사이로 설정 (50 추천)
- 월 1회 정기적으로 재최적화
- 시장 상황이 크게 변했을 때 즉시 재최적화

❌ **피해야 할 것:**
- 과최적화(overfitting): 너무 많은 trials (200+)
- 너무 짧은 백테스팅 기간 (30일 미만)
- 과거 성과만 믿고 실시간 모니터링 소홀

### 2. 이상 탐지

✅ **권장사항:**
- 가격/거래량 이상 탐지는 매 5-10분마다 실행
- 전략 성과는 일 1회 체크
- 리스크 레벨이 "high" 이상이면 거래 일시 중지
- 이상 탐지 알림을 슬랙/텔레그램으로 전송

❌ **피해야 할 것:**
- 너무 민감한 임계값 설정 (거짓 경보 증가)
- 이상 신호 무시
- 자동화만 믿고 수동 점검 소홀

### 3. 운영

✅ **권장사항:**
- 백테스팅과 실제 거래 결과를 비교
- 작은 금액으로 먼저 테스트
- 로그를 정기적으로 검토
- 최적화 이력 보관

❌ **피해야 할 것:**
- 최적화 결과를 검증 없이 바로 적용
- 모든 자금을 한 전략에 집중
- 손실 발생 시 패닉 매도

### 4. 성능 최적화

- Optuna는 많은 리소스를 사용하므로 백그라운드에서 실행
- 여러 전략을 동시에 최적화하지 말 것
- 데이터베이스 쿼리 최적화 (인덱스 활용)

---

## 다음 단계 (단계 2-3)

현재 구현된 기능으로 1-2주 안에 효과를 볼 수 있습니다. 향후 고려할 수 있는 확장:

### 단계 2 (1-2개월)
- **가격 예측 모델**: LSTM/GRU 기반 시계열 예측
- **감성 분석**: 소셜 미디어 데이터 통합

### 단계 3 (2-3개월)
- **강화학습 에이전트**: DQN/PPO를 활용한 자율 매매
- **포트폴리오 최적화**: 멀티 코인 자산 배분

---

## 문제 해결

### 1. 최적화가 너무 느림
- `n_trials` 값을 줄이기 (50 → 30)
- `days_back` 값을 줄이기 (90 → 60)
- 더 빠른 서버/컴퓨터 사용

### 2. "Insufficient data" 오류
- 코인의 거래 기록이 충분한지 확인
- `days_back` 값을 줄이기
- 다른 코인으로 시도

### 3. 최적화 결과가 실제와 다름
- 백테스팅 조건과 실제 거래 조건 차이
- 슬리피지 및 수수료 고려
- 시장 상황 변화

### 4. 이상 탐지가 너무 민감함
- `threshold` 값을 높이기 (3.0 → 4.0)
- `lookback_days`를 늘리기
- 여러 지표를 종합적으로 판단

---

## 라이선스 및 면책 조항

이 시스템은 교육 및 연구 목적으로 제공됩니다. 실제 거래에 사용할 경우:

- 모든 투자 손실에 대한 책임은 사용자에게 있습니다
- 충분한 테스트 후 소액으로 시작하십시오
- 시장 상황을 항상 모니터링하십시오
- 투자는 본인의 판단과 책임 하에 진행하십시오

---

## 지원 및 문의

질문이나 버그 리포트는 GitHub Issues를 통해 제출해주세요.

행복한 트레이딩 되세요! 🚀