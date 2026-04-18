from typing import Optional, Tuple
import logging

from src.srim.models import SRIMResult
from src.database.models import HoldingStage, SignalType

logger = logging.getLogger(__name__)

def evaluate_signal(srim: SRIMResult, holding: Optional[HoldingStage], buy_margin: float = 0.9) -> Tuple[Optional[SignalType], Optional[int]]:
    """
    S-RIM 분석 결과와 현재 보유 상태를 기반으로 매매 시그널을 평가한다.
    반환값: (SignalType, target_price) 시그널이 없을 경우 (None, None)
    """
    # 1. 강제 매도 조건 체크 (예: 현금흐름 위험)
    if holding is not None and srim.cf_risk_count >= 2:
        logger.info(f"[{srim.code}] 강제 매도 조건 충족 (CF위험 {srim.cf_risk_count}회)")
        return SignalType.FORCE_SELL, srim.current_price

    # 2. 보유 중인 종목 매도 시그널 체크
    if holding is not None:
        stage = holding.stage
        
        # 3단계 매도 (최종가격 도달)
        if stage <= 2 and srim.current_price >= srim.last_price:
            return SignalType.SELL_STAGE_3, srim.last_price
            
        # 2단계 매도 (매도가격 도달)
        if stage <= 1 and srim.current_price >= srim.sell_price:
            return SignalType.SELL_STAGE_2, srim.sell_price
            
        # 1단계 매도 (적정가격 도달)
        if stage == 0 and srim.current_price >= srim.proper_price:
            return SignalType.SELL_STAGE_1, srim.proper_price

    # 3. 미보유 종목 매수 시그널 체크
    if holding is None:
        if srim.is_buy_candidate(buy_margin):
            return SignalType.BUY, srim.buy_price
            
    return None, None

def calculate_sell_quantity(holding: HoldingStage, signal_type: SignalType) -> int:
    """시그널 단계에 따라 매도해야 할 수량을 계산한다."""
    if signal_type == SignalType.SELL_STAGE_1:
        # 최초 매수량의 1/3
        return holding.total_buy_qty // 3
    elif signal_type == SignalType.SELL_STAGE_2:
        # 남은 수량의 1/2 (즉, 최초의 1/3)
        return holding.remaining_qty // 2
    elif signal_type in (SignalType.SELL_STAGE_3, SignalType.FORCE_SELL):
        # 전량
        return holding.remaining_qty
        
    return 0
