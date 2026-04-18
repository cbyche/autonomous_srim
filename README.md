# Autonomous S-RIM Trading System

레거시 S-RIM(사경인 님의 잔여이익모델) 종목 분석 로직을 기반으로, 
자동매매 시그널 분석, 포트폴리오(매도 3단계) 관리, 텔레그램 알림, 한국투자증권(KIS) API 자동 주문 기능 등을 제공하는 **완전 자동화 주식 트레이딩 시스템**입니다.

## 주요 기능 (Features)

- **S-RIM 계산 엔진**: FnGuide 크롤링 데이터를 기반으로 ROE 가중평균 및 NPV를 사용해 매수/적정/매도/최종 가격 도출.
- **포트폴리오 스테이지 관리**:
  - 적정가(1단계): 보유량의 1/3 매도
  - 매도가(2단계): 남은 수량의 1/2 매도
  - 최종가(3단계): 전량 매도
- **실시간 모니터링 (스케줄러)**: 장중 정기적으로 감시 종목 가격을 체크하여 시그널을 판별.
- **텔레그램 알림 & 봇**: 시그널 발생 시 텔레그램 알림. (승인/자동 모드 지원 - 인라인 버튼으로 매매 승인 가능)
- **모던 웹 대시보드**: FastAPI와 Jinja2, Glassmorphism UI를 사용한 상태 관리 대시보드 내장.
- **KIS API 연동 (작업중)**: 한국투자증권 Open API를 이용한 시세 조회 및 주문 접수.

## 시작하기 (Getting Started)

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

## 아키텍처 (Architecture)
- **database/**: SQLAlchemy SQLite DB 연동 및 CRUD 레포지토리
- **kis_client/**: 한국투자증권 Open API HTTP 클라이언트 구현체
- **notifier/**: `python-telegram-bot`을 활용한 알림 및 콜백 처리
- **scheduler/**: `APScheduler`를 활용한 장중 폴링 및 배치 작업
- **srim/**: 데이터 크롤링, NPV 기반 가격 도출, 지표 추출 분석 엔진
- **strategy/**: S-RIM 결과와 현재 보유 단계(Holding Stage)를 비교하여 매수/매도 시그널 산출
- **web/**: FastAPI 기반 관리자 대시보드 

## 주의사항
본 시스템은 개인의 투자 편의를 위해 개발되었습니다. 크롤링 대상 사이트의 구조 변경 또는 증권사 API 장애에 따라 오작동할 수 있으며, 실제 투자 손실에 대한 책임은 지지 않습니다.