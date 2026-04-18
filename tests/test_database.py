import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base, SignalType, OrderType, SignalStatus
from src.database.repository import Repository

# 테스트용 인메모리 SQLite DB 사용
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def test_watch_stock_crud(db):
    repo = Repository(db)
    
    # 생성
    stock = repo.add_watch_stock("005930", "삼성전자", "반도체", "메모리", 60000, 70000, 75000, 80000, 90000)
    assert stock.code == "005930"
    assert stock.is_active is True
    assert stock.buy_target_price == 60000
    
    # 조회
    stocks = repo.get_watch_stocks()
    assert len(stocks) == 1
    
    # 업데이트 (동일 코드 추가 시 업데이트됨)
    repo.add_watch_stock("005930", "삼성전자", "반도체", "메모리", 65000, 70000, 75000, 80000, 90000)
    stocks = repo.get_watch_stocks()
    assert len(stocks) == 1
    assert stocks[0].buy_target_price == 65000
    assert stocks[0].sell_target_1 == 70000
    
    # 비활성화
    repo.remove_watch_stock("005930")
    active_stocks = repo.get_watch_stocks(active_only=True)
    assert len(active_stocks) == 0

def test_holding_stage_crud(db):
    repo = Repository(db)
    
    holding = repo.upsert_holding_stage("005930", "삼성전자", stage=0, total_buy_qty=100, remaining_qty=100, avg_buy_price=60000.0)
    assert holding.stage == 0
    
    holding = repo.upsert_holding_stage("005930", "삼성전자", stage=1, total_buy_qty=100, remaining_qty=66, avg_buy_price=60000.0)
    assert holding.stage == 1
    assert holding.remaining_qty == 66
    
    repo.remove_holding_stage("005930")
    assert repo.get_holding_stage("005930") is None

def test_signal_and_order_crud(db):
    repo = Repository(db)
    
    signal = repo.add_signal("005930", "삼성전자", SignalType.BUY, current_price=59000, target_price=60000)
    assert signal.status == SignalStatus.PENDING
    
    pending_signals = repo.get_pending_signals()
    assert len(pending_signals) == 1
    
    repo.update_signal_status(signal.id, SignalStatus.EXECUTED)
    assert repo.get_pending_signals() == []
    
    order = repo.add_order("005930", "삼성전자", OrderType.BUY, qty=100, price=59000, signal_id=signal.id)
    assert order.signal_id == signal.id
    
    orders = repo.get_recent_orders()
    assert len(orders) == 1
    assert orders[0].code == "005930"
