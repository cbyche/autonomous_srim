from typing import Optional, Tuple
import logging

from src.srim.models import SRIMResult
from src.database.models import HoldingStage, SignalType

logger = logging.getLogger(__name__)

def evaluate_signal(srim: SRIMResult, holding: Optional[HoldingStage], required_ror: float, benchmark_amount: float, buy_margin: float = 0.9) -> Tuple[Optional[SignalType], Optional[int]]:
    """
    S-RIM 분석 결과와 현재 보유 상태를 기반으로 매매 시그널을 평가한다.
    benchmark_amount: Stage 0(Full)의 평균 투자 금액 (KRW)
    """
    # 1. 강제 매도 조건 체크 (기업 펀더멘털 훼손 시)
    if holding is not None and srim.should_force_sell(required_ror):
        logger.info(f"[{srim.code}] 펀더멘털 훼손에 따른 전량 처분 시그널 발생")
        return SignalType.FORCE_SELL, srim.current_price

    # 비중 기반 현재 스테이지 역산 (사용자 정의 ≈ 임계치 방식)
    current_ratio = 0.0
    inferred_stage = 0
    if holding:
        current_investment = holding.remaining_qty * holding.avg_buy_price
        current_ratio = current_investment / benchmark_amount if benchmark_amount > 0 else 1.0
        
        if current_ratio > 0.875:
            inferred_stage = 0
        elif 0.625 < current_ratio <= 0.875:
            inferred_stage = 1
        elif 0.375 < current_ratio <= 0.625:
            inferred_stage = 2
        else:
            inferred_stage = 3

    # 2. 매도 시그널 체크 (현재 추정 스테이지보다 높은 목표가 달성 시)
    if holding is not None:
        # 4차 매도
        if inferred_stage <= 3 and srim.current_price >= srim.sell_target_4:
            return SignalType.SELL_STAGE_4, srim.sell_target_4
        # 3차 매도
        if inferred_stage <= 2 and srim.current_price >= srim.sell_target_3:
            return SignalType.SELL_STAGE_3, srim.sell_target_3
        # 2차 매도
        if inferred_stage <= 1 and srim.current_price >= srim.sell_target_2:
            return SignalType.SELL_STAGE_2, srim.sell_target_2
        # 1차 매도
        if inferred_stage == 0 and srim.current_price >= srim.sell_target_1:
            return SignalType.SELL_STAGE_1, srim.sell_target_1

    # 3. 매수 시그널 체크 (미보유 또는 비중 부족 시)
    # 현재가가 매수적정가 * 0.9 미만이고, 비중이 87.5% 미만이면 (추가)매수
    if srim.current_price < srim.buy_target_price * buy_margin:
        if holding is None or current_ratio <= 0.875:
            if srim.is_buy_candidate(required_ror, buy_margin):
                return SignalType.BUY, srim.buy_target_price
            
    return None, None

def calculate_sell_quantity(holding: HoldingStage, signal_type: SignalType, benchmark_amount: float) -> int:
    """시그널 단계에 따라 비중을 조절하기 위해 매도해야 할 수량을 계산한다."""
    if signal_type == SignalType.FORCE_SELL or signal_type == SignalType.SELL_STAGE_4:
        return holding.remaining_qty
        
    avg_price = holding.avg_buy_price
    if avg_price <= 0: return 0
    
    current_inv = holding.remaining_qty * avg_price
    target_ratio = 1.0
    if signal_type == SignalType.SELL_STAGE_1: target_ratio = 0.75
    elif signal_type == SignalType.SELL_STAGE_2: target_ratio = 0.50
    elif signal_type == SignalType.SELL_STAGE_3: target_ratio = 0.25
    
    target_inv = benchmark_amount * target_ratio
    sell_amount = max(0, current_inv - target_inv)
    return int(sell_amount / avg_price)

def calculate_buy_quantity(holding: Optional[HoldingStage], srim: SRIMResult, benchmark_amount: float) -> int:
    """기준 투자금액(Stage 0)까지 채우기 위해 필요한 매수 수량을 계산한다."""
    current_inv = (holding.remaining_qty * holding.avg_buy_price) if holding else 0
    need_inv = max(0, benchmark_amount - current_inv)
    
    if srim.current_price <= 0: return 0
    return int(need_inv / srim.current_price)
