from typing import List, Optional
from sqlalchemy.orm import Session
from src.database.models import WatchStock, HoldingStage, TradeSignal, TradeOrder, SignalStatus

class Repository:
    def __init__(self, db: Session):
        self.db = db

    # --- WatchStock ---
    def get_watch_stocks(self, active_only: bool = True) -> List[WatchStock]:
        query = self.db.query(WatchStock)
        if active_only:
            query = query.filter(WatchStock.is_active == True)
        return query.all()

    def add_watch_stock(self, code: str, name: str, buy_price: Optional[int] = None,
                        proper_price: Optional[int] = None, sell_price: Optional[int] = None,
                        last_price: Optional[int] = None) -> WatchStock:
        stock = self.db.query(WatchStock).filter(WatchStock.code == code).first()
        if not stock:
            stock = WatchStock(code=code, name=name)
            self.db.add(stock)
        
        stock.is_active = True
        stock.buy_price = buy_price
        stock.proper_price = proper_price
        stock.sell_price = sell_price
        stock.last_price = last_price
        
        self.db.commit()
        self.db.refresh(stock)
        return stock

    def remove_watch_stock(self, code: str) -> bool:
        stock = self.db.query(WatchStock).filter(WatchStock.code == code).first()
        if stock:
            stock.is_active = False
            self.db.commit()
            return True
        return False

    # --- HoldingStage ---
    def get_holding_stage(self, code: str) -> Optional[HoldingStage]:
        return self.db.query(HoldingStage).filter(HoldingStage.code == code).first()
        
    def get_all_holding_stages(self) -> List[HoldingStage]:
        return self.db.query(HoldingStage).all()

    def upsert_holding_stage(self, code: str, name: str, stage: int, 
                             total_buy_qty: int, remaining_qty: int, avg_buy_price: float) -> HoldingStage:
        holding = self.db.query(HoldingStage).filter(HoldingStage.code == code).first()
        if not holding:
            holding = HoldingStage(code=code, name=name)
            self.db.add(holding)
            
        holding.stage = stage
        holding.total_buy_qty = total_buy_qty
        holding.remaining_qty = remaining_qty
        holding.avg_buy_price = avg_buy_price
        
        self.db.commit()
        self.db.refresh(holding)
        return holding
        
    def remove_holding_stage(self, code: str):
        holding = self.db.query(HoldingStage).filter(HoldingStage.code == code).first()
        if holding:
            self.db.delete(holding)
            self.db.commit()

    # --- TradeSignal ---
    def add_signal(self, code: str, name: str, signal_type, current_price: int, target_price: int = None) -> TradeSignal:
        signal = TradeSignal(
            code=code,
            name=name,
            signal_type=signal_type,
            current_price=current_price,
            target_price=target_price,
            status=SignalStatus.PENDING
        )
        self.db.add(signal)
        self.db.commit()
        self.db.refresh(signal)
        return signal

    def get_pending_signals(self) -> List[TradeSignal]:
        return self.db.query(TradeSignal).filter(TradeSignal.status == SignalStatus.PENDING).all()

    def update_signal_status(self, signal_id: int, status: SignalStatus) -> Optional[TradeSignal]:
        signal = self.db.query(TradeSignal).filter(TradeSignal.id == signal_id).first()
        if signal:
            signal.status = status
            self.db.commit()
            self.db.refresh(signal)
        return signal

    # --- TradeOrder ---
    def add_order(self, code: str, name: str, order_type, qty: int, price: int, signal_id: int = None) -> TradeOrder:
        order = TradeOrder(
            code=code,
            name=name,
            order_type=order_type,
            qty=qty,
            price=price,
            signal_id=signal_id
        )
        self.db.add(order)
        self.db.commit()
        self.db.refresh(order)
        return order
        
    def get_recent_orders(self, limit: int = 50) -> List[TradeOrder]:
        return self.db.query(TradeOrder).order_by(TradeOrder.executed_at.desc()).limit(limit).all()
