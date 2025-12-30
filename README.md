# Bithumb 자동 거래 전략 시스템

빗썸(Bithumb) 거래소 API를 활용한 암호화폐 자동 거래 전략 시스템입니다.

## 🎯 주요 기능

### 자동 거래 전략
- **Moving Average (이동평균)**: 골든크로스/데드크로스 기반 매매
- **RSI (Relative Strength Index)**: 과매수/과매도 구간 기반 매매
- **Bollinger Bands (볼린저밴드)**: 밴드 상/하단 돌파 기반 매매
- **MACD**: 추세 강도 및 모멘텀 기반 매매 ✨ NEW
- **Stochastic Oscillator**: 스토캐스틱 교차 기반 매매 ✨ NEW
- **Composite Strategy**: 여러 전략을 조합한 확인 신호 기반 매매 ✨ NEW

### 리스크 관리
- **수익 목표 설정** (Profit Target): 목표 수익률 도달 시 자동 매도
- **손절가 설정** (Stop Loss): 손실 한도 도달 시 자동 매도
- **트레일링 스탑** (Trailing Stop): 수익 실현 후 손실 최소화 ✨ NEW

### 백테스팅 ✨ NEW
- 과거 데이터 기반 전략 성능 검증
- 승률, 수익률, 최대 낙폭, 샤프 비율 계산
- 파라미터 최적화 (Grid Search)

## 📁 프로젝트 구조

```
.
├── app/
│   ├── api/
│   │   └── routes/
│   │       ├── analytics.py    # 분석 API
│   │       ├── auth.py          # 인증 API
│   │       └── web.py           # 웹 UI 라우트
│   ├── core/
│   │   ├── config.py            # 설정 관리
│   │   ├── database.py          # 데이터베이스 연결
│   │   └── security.py          # 보안 (JWT 토큰)
│   ├── models/
│   │   ├── database.py          # 데이터베이스 모델
│   │   └── user.py              # 사용자 모델
│   ├── schemas/
│   │   ├── trading.py           # 거래 스키마
│   │   └── user.py              # 사용자 스키마
│   ├── services/
│   │   ├── backtesting.py       # 백테스팅 엔진 ✨ NEW
│   │   ├── bithumb_api.py       # 빗썸 API 래퍼
│   │   ├── scheduler.py         # 전략 실행 스케줄러
│   │   ├── strategy.py          # 거래 전략 구현
│   │   └── trading_engine.py    # 거래 실행 엔진
│   ├── templates/               # Jinja2 템플릿
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── register.html
│   │   └── strategy.html
│   ├── utils/
│   │   └── helpers.py           # 유틸리티 함수
│   └── main.py                  # FastAPI 앱 진입점
├── .env.example                 # 환경 변수 예시
├── pyproject.toml               # 프로젝트 설정
└── README.md                    # 프로젝트 문서
```

## 🚀 설치 및 실행

### 1. 환경 설정

```bash
# 저장소 클론
git clone <repository-url>
cd bithumb_jhsun

# 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 빗썸 API 키를 입력하세요
```

### 2. 의존성 설치

```bash
# uv 패키지 매니저 사용 (권장)
uv pip install -e .

# 또는 pip 사용
pip install -e .
```

### 3. 실행

```bash
# FastAPI 서버 시작
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 웹 브라우저에서 접속
# http://localhost:8000
```

## 📖 사용 방법

### 1. 전략 생성

웹 UI (`/strategy`)에서 전략을 생성합니다:

**Moving Average 전략 예시:**
- 코인: BTC
- Short Period: 5일
- Long Period: 20일
- 거래 금액: 100,000 KRW
- 목표 수익률: 5%
- 손절가: 3%

**MACD 전략 예시:**
- 코인: ETH
- Fast Period: 12일
- Slow Period: 26일
- Signal Period: 9일
- 거래 금액: 50,000 KRW
- 목표 수익률: 7%
- 손절가: 4%

### 2. 백테스팅

전략을 실제 적용하기 전에 백테스팅으로 성능을 검증하세요:

```python
from app.services.backtesting import Backtester
from app.services.strategy import MACDStrategy
from app.services.bithumb_api import bithumb_api

# 백테스터 초기화
backtester = Backtester(bithumb_api)

# 전략 생성
strategy = MACDStrategy(bithumb_api, fast_period=12, slow_period=26, signal_period=9)

# 백테스트 실행
result = backtester.run_backtest(
    strategy=strategy,
    coin="BTC",
    initial_balance=1000000,  # 100만원
    days=30,                   # 30일간
    fee_rate=0.0025            # 0.25% 수수료
)

# 결과 출력
print(f"총 수익률: {result.total_return_pct:.2f}%")
print(f"승률: {result.win_rate:.2f}%")
print(f"최대 낙폭: {result.max_drawdown:.2f}%")
print(f"샤프 비율: {result.sharpe_ratio:.2f}")
```

### 3. 파라미터 최적화

최적의 파라미터를 찾기 위해 Grid Search를 실행할 수 있습니다:

```python
# 파라미터 범위 정의
param_ranges = {
    "fast_period": [8, 12, 16],
    "slow_period": [20, 26, 32],
    "signal_period": [7, 9, 11]
}

# 최적화 실행
optimization_result = backtester.optimize_parameters(
    strategy_class=MACDStrategy,
    coin="BTC",
    param_ranges=param_ranges,
    initial_balance=1000000,
    days=60
)

# 최적 파라미터 출력
print("최적 파라미터:", optimization_result["best_params"])
print("최고 수익률:", optimization_result["best_return_pct"])
```

## 📊 전략 상세 설명

### 1. Moving Average (MA)
- **매수 신호**: 단기 이동평균선이 장기 이동평균선을 상향 돌파 (골든크로스)
- **매도 신호**: 단기 이동평균선이 장기 이동평균선을 하향 돌파 (데드크로스)
- **파라미터**: `short_period` (기본값: 5), `long_period` (기본값: 20)

### 2. RSI (Relative Strength Index)
- **매수 신호**: RSI가 과매도 기준선(기본값: 30) 이하에서 상승
- **매도 신호**: RSI가 과매수 기준선(기본값: 70) 이상에서 하락
- **파라미터**: `period` (기본값: 14), `oversold` (기본값: 30), `overbought` (기본값: 70)

### 3. Bollinger Bands
- **매수 신호**: 가격이 하단 밴드를 상향 돌파
- **매도 신호**: 가격이 상단 밴드를 하향 돌파
- **파라미터**: `period` (기본값: 20), `std_dev` (기본값: 2.0)

### 4. MACD ✨ NEW
- **매수 신호**: MACD 라인이 시그널 라인을 상향 돌파 (Bullish Crossover)
- **매도 신호**: MACD 라인이 시그널 라인을 하향 돌파 (Bearish Crossover)
- **파라미터**: `fast_period` (기본값: 12), `slow_period` (기본값: 26), `signal_period` (기본값: 9)

### 5. Stochastic Oscillator ✨ NEW
- **매수 신호**: %K 라인이 %D 라인을 과매도 구간(기본값: 20 이하)에서 상향 돌파
- **매도 신호**: %K 라인이 %D 라인을 과매수 구간(기본값: 80 이상)에서 하향 돌파
- **파라미터**: `k_period` (기본값: 14), `d_period` (기본값: 3), `oversold` (기본값: 20), `overbought` (기본값: 80)

### 6. Composite Strategy ✨ NEW
- **매수/매도 신호**: 설정된 여러 전략 중 최소 `min_confirmations`개 이상이 동일한 신호 발생 시
- **예시**: RSI와 Bollinger Bands 모두 매수 신호 발생 시에만 매수
- **파라미터**: `strategies` (전략 리스트), `min_confirmations` (기본값: 2)

## 📝 주요 변경 사항 (2025-12-29)

### ✨ 추가된 기능
1. **새로운 전략**:
   - MACD 전략 (추세 강도 및 모멘텀 기반)
   - Stochastic 전략 (과매수/과매도 판단)
   - Composite 전략 (여러 전략 조합)

2. **백테스팅 시스템**:
   - 과거 데이터 기반 전략 성능 검증
   - 승률, 수익률, 최대 낙폭, 샤프 비율 자동 계산
   - Grid Search를 통한 파라미터 최적화

3. **트레일링 스탑**:
   - 데이터베이스 모델에 `highest_price` 필드 추가
   - 향후 트레일링 스탑 로직 구현 예정

### ❌ 제거된 기능
1. **수동 거래 UI 및 API** 삭제:
   - `/trade` 페이지 제거
   - `/dashboard` 페이지 제거
   - `/api/trading/*` 엔드포인트 제거
   - `/api/orders/*` 엔드포인트 제거

2. **삭제된 파일**:
   - `app/api/routes/trading.py`
   - `app/api/routes/orders.py`
   - `app/templates/trade.html`
   - `app/templates/dashboard.html`

**⚠️ 중요**: 이제 시스템은 **자동 전략 실행에만 집중**합니다. 수동 거래가 필요한 경우 빗썸 웹사이트나 앱을 직접 이용하세요.

## 🔌 API 엔드포인트

### 전략 관리
- `GET /strategy` - 전략 관리 페이지
- `POST /strategy/ma` - Moving Average 전략 생성
- `POST /strategy/rsi` - RSI 전략 생성
- `POST /strategy/bollinger` - Bollinger Bands 전략 생성
- `POST /strategy/toggle/{id}` - 전략 활성화/비활성화
- `POST /strategy/delete/{id}` - 전략 삭제

### 분석
- `GET /api/analytics/execution-logs` - 전략 실행 로그 조회
- `GET /api/analytics/execution-summary` - 전략 실행 요약

### 인증
- `POST /api/auth/login` - 로그인
- `POST /api/auth/register` - 회원가입
- `GET /logout` - 로그아웃

## 🔐 환경 변수

`.env` 파일에서 다음 변수를 설정하세요:

```env
# Bithumb API
BITHUMB_API_KEY=your_api_key_here
BITHUMB_SECRET_KEY=your_secret_key_here

# Database
DATABASE_URL=sqlite:///./db/trading.db

# Security
SECRET_KEY=your-secret-key-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Trading
TRADING_ENABLED=true
SCHEDULER_ENABLED=true
SCHEDULER_INTERVAL_SECONDS=60
```

## ⚠️ 보안 주의사항

1. `.env` 파일을 절대 Git에 커밋하지 마세요
2. API 키는 읽기 전용 권한만 부여하세요
3. 프로덕션 환경에서는 반드시 강력한 `SECRET_KEY`를 사용하세요
4. HTTPS를 사용하여 통신을 암호화하세요

## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.

## 🤝 기여

버그 리포트, 기능 제안, Pull Request는 언제나 환영합니다!

## ⚖️ 면책 조항

이 소프트웨어는 교육 목적으로 제공됩니다. 실제 거래에서 발생하는 손실에 대해 개발자는 책임을 지지 않습니다. 자동 거래는 높은 리스크를 수반하므로, 충분한 테스트 후 신중하게 사용하세요.