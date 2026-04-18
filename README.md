# Autonomous S-RIM Trading System

레거시 S-RIM(사경인 님의 잔여이익모델) 종목 분석 로직을 고도화하여, 사용자 정의의 엄격한 펀더멘털 필터링, 지능형 비중 역산 알고리즘, 한국투자증권(KIS) API 연동까지 갖춘 **완전 자동화 '포트폴리오 어웨어(Portfolio-aware)' 주식 트레이딩 시스템**입니다.

## 🌟 주요 기능 (Features)

- **엄격한 매수 필터링 (11 conditions)**: 단순 저평가가 아닌 ROE, 현금흐름, 적자여부, 배당, 그리고 WICS 업종(지주사, 금융 등 제외)까지 11가지의 엄격한 조건을 모두 통과한 종목만 매수합니다.
- **안전장치 (Force Sell)**: 수익 구간 여부와 상관없이, 기업의 펀더멘털(ROE 훼손, 적자 전환 등)이 망가지면 즉시 전량 매도하여 손실을 차단합니다.
- **포트폴리오 스테이지 역산 관리**: 
  - 주가 등락에 따른 혼동을 막기 위해 **현재 투자 원금 비중**을 역산하여 종목의 현재 Stage(0~3)를 지능적으로 추론합니다.
  - 목표가에 도달하면 25%씩 4단계로 분할 매도하여 수익을 극대화합니다.
  - 매도 후 주가가 다시 떨어지면 부족한 비중(100% 목표)만큼 다시 추가 매수하는 순환 매매를 수행합니다.
- **종합 점수(Mix Score) 랭킹 시스템**:
  - `안전마진(Buy Yield) 50% + 품질(ROE/Ke) 50%` 가중치를 두어 매수 후보의 우선순위를 정합니다.
  - 자금 제한 시 **1순위(비중 복구 추가매수) -> 2순위(점수 높은 신규 종목)** 순으로 배분하며 미수를 방지합니다.
- **스마트 스케줄링 및 안티봇 우회**:
  - FnGuide 차단 방지를 위해 새벽 시간대(3 AM 보유 종목, 4 AM KRX 전체)에만 재무 데이터를 스크래핑합니다.
  - 장중에는 KIS API로 실시간 현재가만 불러와 신속하게 매매를 집행합니다.
- **한국투자증권(KIS) API 실전 매매**: 가상 매매가 아닌 실제 증권사 서버와 통신하여 실시간 현재가를 가져오고 자동 매매 주문을 발송합니다.
- **모던 웹 대시보드 & 텔레그램**: FastAPI 대시보드로 실시간 설정을 변경하고(스케줄러 즉각 반영), 텔레그램 봇으로 알림 및 수동 승인을 수행합니다.

## 🚀 시작하기 (Getting Started)

### 1. 요구사항
- Python 3.11 이상
- `uv` 패키지 매니저 권장

### 2. 설치
```bash
# 가상환경 생성 및 의존성 설치
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

### 3. 환경 설정
`config/config.example.yaml` 파일을 `config/config.yaml`로 복사하고, 필요한 키값(KIS App Key, Telegram Token 등)을 입력하세요.
```bash
cp config/config.example.yaml config/config.yaml
```

### 4. 실행 방법
CLI 통합 진입점(`src/main.py`)을 제공합니다.

```bash
# 전체 기능(웹 대시보드, 텔레그램 봇, 스케줄러) 동시 실행
uv run python -m src.main --all

# 웹 대시보드만 실행 (http://localhost:8000)
uv run python -m src.main --web

# 텔레그램 봇만 실행
uv run python -m src.main --bot
```

## 🏗️ 아키텍처 (Architecture)
- **database/**: SQLAlchemy SQLite DB 연동 및 CRUD 레포지토리
- **kis_client/**: 한국투자증권 Open API (시세 조회 및 주문 접수)
- **notifier/**: 텔레그램 봇을 통한 알림 및 인라인 콜백 승인 체계
- **scheduler/**: APScheduler를 활용한 새벽 스크래핑 배치 및 장중 가격 모니터링
- **srim/**: FnGuide 스크래핑(지연 로직 포함), 잔여이익모델(NPV) 기반 목표가/수익률 계산 
- **strategy/**: 비중 역산, Mix Score 랭킹, 가용 자금 통제 및 KIS 주문 실행을 관리하는 매매 뇌(Brain)
- **web/**: FastAPI 기반 관리자 대시보드 및 설정 변경 API

## ⚠️ 주의사항
본 시스템은 철저히 사용자 맞춤형 전략을 구현하기 위해 개발되었습니다. 증권사 API 장애 또는 크롤링 대상 사이트의 구조 변경 시 오작동할 수 있으며, 본 시스템을 이용한 실제 투자 손실에 대한 책임은 지지 않습니다.