import pytest

from src.database.models import HoldingStage, SignalType
from src.srim.models import SRIMResult
from src.strategy.signal import evaluate_signal, calculate_sell_quantity, calculate_buy_quantity

@pytest.fixture
def mock_srim():
    return SRIMResult(
        code="005930", name="삼성전자", industry="IT", product="반도체",
        current_price=65000, 
        buy_target_price=60000, 
        sell_target_1=70000,
        sell_target_2=75000,
        sell_target_3=80000,
        sell_target_4=90000,
        buy_yield=0, target_1_yield=0, target_2_yield=0, target_3_yield=0, target_4_yield=0,
        roe=10.0, roe_reference="",
        dividend_yield=2.0, dividend_payout_ratio=30.0, cf_risk_count=0,
        cf_to_op_avg=0.9, net_income_4q_sum=1000, net_income_deficit_count=0,
        op_income_4q_sum=1200, op_income_deficit_count=0
    )

def test_evaluate_signal_buy_and_addon(mock_srim):
    benchmark = 1000000.0 # 100만원 기준
    
    # 1. 신규 매수 (비중 0%)
    mock_srim.current_price = 53000
    sig, target = evaluate_signal(mock_srim, holding=None, required_ror=8.0, benchmark_amount=benchmark)
    assert sig == SignalType.BUY
    
    # 2. 추가 매수 (비중이 50%인 상태에서 가격 하락 시)
    holding = HoldingStage(
        code="005930", name="삼성전자", 
        total_buy_qty=10, remaining_qty=10, avg_buy_price=50000.0 # 50만원 보유 (50%)
    )
    mock_srim.current_price = 53000 # 매수권
    sig, target = evaluate_signal(mock_srim, holding, required_ror=8.0, benchmark_amount=benchmark)
    assert sig == SignalType.BUY
    
    # 3. 추가 매수 안함 (이미 비중이 100%인 경우)
    holding.remaining_qty = 20 # 100만원 보유 (100%)
    sig, target = evaluate_signal(mock_srim, holding, required_ror=8.0, benchmark_amount=benchmark)
    assert sig is None

def test_evaluate_signal_ratio_based_sell(mock_srim):
    benchmark = 1000000.0
    # 비중이 75%인 상태 (이미 1차 매도 완료된 것으로 간주)
    holding = HoldingStage(
        code="005930", name="삼성전자", 
        total_buy_qty=20, remaining_qty=15, avg_buy_price=50000.0 # 75만원 보유
    )
    
    # 1차 매도가 도달해도 시그널 없음 (이미 75%이므로)
    mock_srim.current_price = 70000 # 1차 매도가
    sig, target = evaluate_signal(mock_srim, holding, required_ror=8.0, benchmark_amount=benchmark)
    assert sig is None
    
    # 2차 매도가 도달 시 시그널 발생
    mock_srim.current_price = 76000 # 2차 매도가
    sig, target = evaluate_signal(mock_srim, holding, required_ror=8.0, benchmark_amount=benchmark)
    assert sig == SignalType.SELL_STAGE_2

def test_calculate_quantities():
    benchmark = 1000000.0
    holding = HoldingStage(code="005930", name="삼성전자", total_buy_qty=20, remaining_qty=10, avg_buy_price=50000.0)
    
    # 추가 매수 수량: 100만원 채우려면 50만원 더 사야함 (가격 5만원 가정)
    mock_srim = SRIMResult(code="005930", name="삼성전자", industry="", product="", current_price=50000, buy_target_price=60000, sell_target_1=70000, sell_target_2=75000, sell_target_3=80000, sell_target_4=90000, buy_yield=0, target_1_yield=0, target_2_yield=0, target_3_yield=0, target_4_yield=0, roe=10.0, roe_reference="", dividend_yield=2.0, dividend_payout_ratio=30.0, cf_risk_count=0, cf_to_op_avg=0.9, net_income_4q_sum=1000, net_income_deficit_count=0, op_income_4q_sum=1200, op_income_deficit_count=0)
    
    buy_qty = calculate_buy_quantity(holding, mock_srim, benchmark)
    assert buy_qty == 10 # 50만원 / 5만원 = 10주
    
    # 2차 매도 수량: 현재 10주(50%)에서 2차 매도 시 목표는 50%이므로 0주? 
    # 아, 테스트를 위해 현재 20주(100%)인 상황으로 변경
    holding.remaining_qty = 20
    sell_qty = calculate_sell_quantity(holding, SignalType.SELL_STAGE_2, benchmark)
    assert sell_qty == 10 # 100만원 -> 50만원 (10주 매도)
