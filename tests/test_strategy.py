import pytest

from src.database.models import HoldingStage, SignalType
from src.srim.models import SRIMResult
from src.strategy.signal import evaluate_signal, calculate_sell_quantity

@pytest.fixture
def mock_srim():
    return SRIMResult(
        code="005930", name="삼성전자", industry="", product="",
        current_price=65000, buy_price=60000, proper_price=70000,
        sell_price=80000, last_price=90000, buy_yield=0, proper_yield=0,
        sell_yield=0, last_yield=0, roe=10.0, roe_reference="",
        dividend_yield=0, dividend_payout_ratio=0, cf_risk_count=0,
        cf_to_op_avg=0, net_income_4q_sum=0, net_income_deficit_count=0,
        op_income_4q_sum=0, op_income_deficit_count=0
    )

def test_evaluate_signal_buy(mock_srim):
    # 가격이 매수 기준가 (60000 * 0.9 = 54000) 보다 낮아야 BUY
    mock_srim.current_price = 53000
    sig, target = evaluate_signal(mock_srim, holding=None, buy_margin=0.9)
    assert sig == SignalType.BUY
    assert target == 60000
    
    # 높으면 None
    mock_srim.current_price = 55000
    sig, target = evaluate_signal(mock_srim, holding=None, buy_margin=0.9)
    assert sig is None

def test_evaluate_signal_sell_stages(mock_srim):
    holding = HoldingStage(code="005930", name="삼성전자", stage=0, total_buy_qty=100, remaining_qty=100)
    
    # 1단계 매도 (적정가 도달)
    mock_srim.current_price = 70000
    sig, target = evaluate_signal(mock_srim, holding)
    assert sig == SignalType.SELL_STAGE_1
    assert target == 70000
    
    # 이미 1단계 매도했으면 1단계는 패스, 2단계 기다림
    holding.stage = 1
    sig, target = evaluate_signal(mock_srim, holding)
    assert sig is None
    
    # 2단계 매도 (매도가 도달)
    mock_srim.current_price = 85000
    sig, target = evaluate_signal(mock_srim, holding)
    assert sig == SignalType.SELL_STAGE_2
    assert target == 80000
    
    # 3단계 매도 (최종가 도달)
    holding.stage = 2
    mock_srim.current_price = 95000
    sig, target = evaluate_signal(mock_srim, holding)
    assert sig == SignalType.SELL_STAGE_3
    assert target == 90000

def test_calculate_sell_quantity():
    holding = HoldingStage(code="005930", name="삼성전자", stage=0, total_buy_qty=300, remaining_qty=300)
    
    # 1단계: 총 300의 1/3 = 100
    assert calculate_sell_quantity(holding, SignalType.SELL_STAGE_1) == 100
    
    # 2단계: 100주 팔았다고 가정하고 200주 남음. 남은 것의 1/2 = 100
    holding.remaining_qty = 200
    holding.stage = 1
    assert calculate_sell_quantity(holding, SignalType.SELL_STAGE_2) == 100
    
    # 3단계: 남은 전량
    holding.remaining_qty = 100
    holding.stage = 2
    assert calculate_sell_quantity(holding, SignalType.SELL_STAGE_3) == 100
