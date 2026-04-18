# Autonomous S-RIM 진행 상황

## Phase 1: 프로젝트 기반 구조
- [x] pyproject.toml (의존성 정의)
- [x] config/config.example.yaml (설정 템플릿)
- [x] .gitignore 업데이트
- [x] src/ 패키지 구조 생성
- [x] 설정 로더 (src/config.py)
- [x] requirements.md (요구사항 문서)
- [x] progress.md (진행 체크리스트)

## Phase 2: S-RIM 계산 엔진
- [x] src/srim/models.py (데이터 모델)
- [x] src/srim/calculator.py (가격 계산 로직)
- [x] src/srim/data_fetcher.py (데이터 수집)
- [x] src/srim/analyzer.py (종목 분석기)
- [x] 레거시 CSV 기반 검증 테스트

## Phase 3: 데이터베이스
- [x] src/database/models.py (ORM 모델)
- [x] src/database/repository.py (CRUD)

## Phase 4: 매매 전략 엔진
- [x] src/strategy/signal.py (시그널 정의)
- [x] src/strategy/portfolio_manager.py (포트폴리오 관리)

## Phase 5: 웹 대시보드
- [x] src/web/app.py (FastAPI 앱)
- [x] src/web/api/ (REST API 라우터)
- [x] src/web/static/ (프론트엔드)

## Phase 6: 스케줄러 + 알림
- [x] src/scheduler/jobs.py (APScheduler)
- [x] src/notifier/telegram_bot.py (텔레그램)

## Phase 7: 한국투자증권 API 클라이언트
- [x] src/kis_client/auth.py (인증)
- [x] src/kis_client/market.py (시세 조회)
- [x] src/kis_client/account.py (계좌/주문)

## Phase 8: 통합 + 문서화
- [x] src/main.py (CLI 진입점)
- [x] README.md 업데이트
- [x] E2E 테스트 (Dry-run 수준 검증)

## Phase 9: 전략 고도화 (Refinement)
- [x] 매도 4단계 세분화 (25% 분할 매도)
- [x] 직관적 용어 리팩토링 (매수적정가, 1~4차 매도가)
- [x] DB 스키마 업데이트 및 UI 용어 반영
- [x] 변경 로직 테스트 코드 검증 완료
