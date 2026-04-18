from typing import List
import logging
from sqlalchemy.orm import Session

from src.database.repository import Repository
from src.database.models import TradeSignal, SignalType, SignalStatus, OrderType
from src.srim.analyzer import analyze_stock
from src.strategy.signal import evaluate_signal, calculate_sell_quantity
from src.config import get_config_value

logger = logging.getLogger(__name__)

class PortfolioManager:
    def __init__(self, db: Session, config: dict):
        self.repo = Repository(db)
        self.config = config
        self.required_ror = get_config_value(config, "trading", "required_ror_percent", default=8.0)
        self.buy_margin = get_config_value(config, "trading", "buy_margin", default=0.9)

    def scan_watch_stocks(self):
        """감시 종목 리스트를 순회하며 S-RIM 분석을 수행하고 시그널을 생성한다."""
        watch_stocks = self.repo.get_watch_stocks(active_only=True)
        
        for stock in watch_stocks:
            logger.info(f"[{stock.code}] {stock.name} 분석 시작...")
            
            # TODO: 업종, 주요제품 등은 KRX 리스트에서 가져와야 하지만 여기선 임시값 사용
            srim_result = analyze_stock(stock.code, stock.name, "", "", self.required_ror)
            if not srim_result:
                continue
                
            # 최신 가격 정보 DB 업데이트
            self.repo.add_watch_stock(
                stock.code, stock.name, 
                buy_price=srim_result.buy_price,
                proper_price=srim_result.proper_price,
                sell_price=srim_result.sell_price,
                last_price=srim_result.last_price
            )
            
            holding = self.repo.get_holding_stage(stock.code)
            
            signal_type, target_price = evaluate_signal(srim_result, holding, self.buy_margin)
            
            if signal_type:
                logger.info(f"[{stock.code}] 신규 시그널 발생: {signal_type.value} (목표가: {target_price}, 현재가: {srim_result.current_price})")
                self.repo.add_signal(
                    stock.code, stock.name, signal_type, 
                    current_price=srim_result.current_price, target_price=target_price
                )

    def execute_signal(self, signal_id: int, execution_price: int, execution_qty: int):
        """
        발생한 시그널을 실행(매수/매도 완료) 처리한다.
        실제 KIS API 주문이 완료된 후 이 함수가 호출되어야 한다.
        """
        signal = self.repo.db.query(TradeSignal).filter(TradeSignal.id == signal_id).first()
        if not signal or signal.status != SignalStatus.PENDING:
            return False
            
        order_type = OrderType.BUY if signal.signal_type == SignalType.BUY else OrderType.SELL
        
        # 주문 히스토리 추가
        self.repo.add_order(
            signal.code, signal.name, order_type, execution_qty, execution_price, signal_id
        )
        
        # 보유 상태 업데이트
        holding = self.repo.get_holding_stage(signal.code)
        
        if signal.signal_type == SignalType.BUY:
            if not holding:
                self.repo.upsert_holding_stage(
                    signal.code, signal.name, stage=0, 
                    total_buy_qty=execution_qty, remaining_qty=execution_qty, avg_buy_price=execution_price
                )
            else:
                # 추가 매수
                new_total = holding.total_buy_qty + execution_qty
                new_remain = holding.remaining_qty + execution_qty
                new_avg = ((holding.avg_buy_price * holding.remaining_qty) + (execution_price * execution_qty)) / new_remain
                self.repo.upsert_holding_stage(
                    signal.code, signal.name, stage=holding.stage,
                    total_buy_qty=new_total, remaining_qty=new_remain, avg_buy_price=new_avg
                )
                
        else: # SELL
            if holding:
                new_remain = max(0, holding.remaining_qty - execution_qty)
                
                # 스테이지 업데이트
                new_stage = holding.stage
                if signal.signal_type == SignalType.SELL_STAGE_1:
                    new_stage = 1
                elif signal.signal_type == SignalType.SELL_STAGE_2:
                    new_stage = 2
                elif signal.signal_type in (SignalType.SELL_STAGE_3, SignalType.FORCE_SELL):
                    new_stage = 3
                    
                if new_remain == 0:
                    self.repo.remove_holding_stage(signal.code)
                else:
                    self.repo.upsert_holding_stage(
                        signal.code, signal.name, stage=new_stage,
                        total_buy_qty=holding.total_buy_qty, remaining_qty=new_remain, avg_buy_price=holding.avg_buy_price
                    )
        
        self.repo.update_signal_status(signal_id, SignalStatus.EXECUTED)
        return True
