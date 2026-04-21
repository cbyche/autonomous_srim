"""
잔고 동기화(Hard-Sync) 테스트

시나리오:
1. 증권사에 없는 종목 → 로컬 DB에서 삭제
2. 수량 불일치 → 증권사 데이터로 수량 및 Stage 재추론 후 덮어씌움
3. 완전 일치 → 아무것도 변경 안 함
4. Mock 모드(빈 dict 반환) → 동기화 스킵 (DB 그대로 유지)
"""
import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, HoldingStage
from src.database.repository import Repository
from src.strategy.portfolio_manager import PortfolioManager


# ── 인메모리 DB 픽스처 ────────────────────────────────────────────────────────
@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# ── PortfolioManager Mock 픽스처 ──────────────────────────────────────────────
@pytest.fixture
def manager(db):
    """KIS 클라이언트를 Mock으로 대체한 PortfolioManager"""
    config = {
        "trading": {
            "required_ror_percent": 8.0,
            "buy_margin": 0.9,
            "is_mock": True,
            "base_investment_amount": 1_000_000,
        },
        "kis_api": {"account_no": "0000000001"},
    }

    with patch("src.strategy.portfolio_manager.KISAuth"), \
         patch("src.strategy.portfolio_manager.KISMarket"):
        mgr = PortfolioManager(db=db, config=config)
        # KISAccount는 테스트마다 직접 교체
        mgr.kis_account = MagicMock()
    return mgr


# ── 헬퍼: DB에 HoldingStage 삽입 ─────────────────────────────────────────────
def _insert_holding(db, code, name, qty, avg_price, stage=0):
    h = HoldingStage(
        code=code, name=name,
        total_buy_qty=qty, remaining_qty=qty,
        avg_buy_price=float(avg_price), stage=stage
    )
    db.add(h)
    db.commit()
    return h


# ══════════════════════════════════════════════════════════════════════════════
# 시나리오 1: 증권사에 없는 종목 → 로컬 DB 삭제 (빈 계좌 동기화)
# ══════════════════════════════════════════════════════════════════════════════
def test_sync_removes_missing_stock(db, manager):
    """증권사에 없는 종목은 로컬 DB HoldingStage에서 제거되어야 한다. (빈 계좌 시나리오 포함)"""
    _insert_holding(db, "005930", "삼성전자", qty=10, avg_price=70_000)
    
    # 증권사 잔고: 깡통 계좌 (빈 dict 반환)
    manager.kis_account.get_balance.return_value = {}

    manager.sync_balance_with_broker()

    remaining = db.query(HoldingStage).filter(HoldingStage.code == "005930").first()
    assert remaining is None, "빈 계좌 반환 시 로컬 DB가 초기화되지 않았습니다."


# ══════════════════════════════════════════════════════════════════════════════
# 시나리오 2: 수량 불일치 → 증권사 데이터로 업데이트 및 Stage 재추론
# ══════════════════════════════════════════════════════════════════════════════
def test_sync_updates_mismatched_quantity(db, manager):
    """수량이 다를 경우 증권사 데이터로 remaining_qty와 Stage가 갱신되어야 한다."""
    # DB: 20주(100%, Stage 0) → 증권사: 15주(75%, Stage 1)
    _insert_holding(db, "005930", "삼성전자", qty=20, avg_price=50_000, stage=0)

    # benchmark: 100만원(기본 설정값), 15주×50,000원=750,000원 → 비중 75% → Stage 1
    manager.kis_account.get_balance.return_value = {
        "005930": {"qty": 15, "avg_price": 50_000}
    }
    manager.sync_balance_with_broker()

    updated = db.query(HoldingStage).filter(HoldingStage.code == "005930").first()
    assert updated is not None
    assert updated.remaining_qty == 15, "remaining_qty가 증권사 데이터로 갱신되지 않았습니다."
    assert updated.stage == 1, f"Stage가 1로 재추론되지 않았습니다. 실제: {updated.stage}"


# ══════════════════════════════════════════════════════════════════════════════
# 시나리오 3: 완전 일치 → DB 변경 없음
# ══════════════════════════════════════════════════════════════════════════════
def test_sync_no_change_when_matched(db, manager):
    """DB와 증권사 잔고가 일치하면 아무것도 변경되지 않아야 한다."""
    _insert_holding(db, "005930", "삼성전자", qty=20, avg_price=50_000, stage=0)

    manager.kis_account.get_balance.return_value = {
        "005930": {"qty": 20, "avg_price": 50_000}
    }
    manager.sync_balance_with_broker()

    holding = db.query(HoldingStage).filter(HoldingStage.code == "005930").first()
    assert holding.remaining_qty == 20
    assert holding.stage == 0


# ══════════════════════════════════════════════════════════════════════════════
# 시나리오 4: Mock 모드 (None) → 동기화 스킵, DB 그대로 유지
# ══════════════════════════════════════════════════════════════════════════════
def test_sync_skips_on_none_balance(db, manager):
    """get_balance가 None을 반환하면 동기화가 스킵되고 DB가 그대로 유지된다."""
    _insert_holding(db, "005930", "삼성전자", qty=10, avg_price=70_000, stage=0)

    manager.kis_account.get_balance.return_value = None
    manager.sync_balance_with_broker()

    # DB 변경 없어야 함
    holding = db.query(HoldingStage).filter(HoldingStage.code == "005930").first()
    assert holding is not None, "Mock 모드에서 동기화 스킵이 되지 않았습니다."
    assert holding.remaining_qty == 10

# ══════════════════════════════════════════════════════════════════════════════
# 시나리오 5: 수동 HTS 매수 → 로컬 DB에 Stage 0으로 신규 등록
# ══════════════════════════════════════════════════════════════════════════════
def test_sync_adds_manual_purchase(db, manager):
    """로컬 DB에 없는 종목이 증권사 잔고에 있으면 새로 편입되어야 한다."""
    # DB 빈 상태
    manager.kis_account.get_balance.return_value = {
        "000660": {"qty": 5, "avg_price": 150_000}
    }
    manager.sync_balance_with_broker()

    holding = db.query(HoldingStage).filter(HoldingStage.code == "000660").first()
    assert holding is not None, "수동 매수 종목이 DB에 추가되지 않았습니다."
    assert holding.remaining_qty == 5
    assert holding.stage == 0
