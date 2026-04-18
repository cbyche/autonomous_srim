from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Enum
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()

class SignalType(enum.Enum):
    BUY = "buy"
    SELL_STAGE_1 = "sell_stage_1"
    SELL_STAGE_2 = "sell_stage_2"
    SELL_STAGE_3 = "sell_stage_3"
    FORCE_SELL = "force_sell"

class OrderType(enum.Enum):
    BUY = "buy"
    SELL = "sell"

class SignalStatus(enum.Enum):
    PENDING = "pending"
    EXECUTED = "executed"
    REJECTED = "rejected"
    FAILED = "failed"

class WatchStock(Base):
    """감시/매수 후보 종목"""
    __tablename__ = "watch_stocks"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True)  # 감시 활성화 여부
    added_at = Column(DateTime, default=datetime.utcnow)
    
    # S-RIM 최신 분석 가격 캐싱
    buy_price = Column(Integer, nullable=True)
    proper_price = Column(Integer, nullable=True)
    sell_price = Column(Integer, nullable=True)
    last_price = Column(Integer, nullable=True)
    
class HoldingStage(Base):
    """보유 종목별 매도 단계 추적"""
    __tablename__ = "holding_stages"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, index=True, nullable=False)
    name = Column(String(50), nullable=False)
    stage = Column(Integer, default=0)  # 0: 매수직후, 1: 1단계 매도(1/3), 2: 2단계 매도(1/2), 3: 전량 매도
    
    total_buy_qty = Column(Integer, nullable=False)   # 최초 총 매수 수량
    remaining_qty = Column(Integer, nullable=False)   # 현재 남은 수량
    avg_buy_price = Column(Float, nullable=False)     # 매수 평균가
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TradeSignal(Base):
    """매매 시그널 히스토리"""
    __tablename__ = "trade_signals"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), index=True, nullable=False)
    name = Column(String(50), nullable=False)
    
    signal_type = Column(Enum(SignalType), nullable=False)
    status = Column(Enum(SignalStatus), default=SignalStatus.PENDING)
    
    current_price = Column(Integer, nullable=False)
    target_price = Column(Integer, nullable=True)  # 매수/매도 기준이 된 가격
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    orders = relationship("TradeOrder", back_populates="signal")

class TradeOrder(Base):
    """주문 실행 히스토리"""
    __tablename__ = "trade_orders"
    
    id = Column(Integer, primary_key=True, index=True)
    signal_id = Column(Integer, ForeignKey("trade_signals.id"), nullable=True)
    
    code = Column(String(10), index=True, nullable=False)
    name = Column(String(50), nullable=False)
    
    order_type = Column(Enum(OrderType), nullable=False)
    qty = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)  # 주문 단가
    
    executed_at = Column(DateTime, default=datetime.utcnow)
    
    signal = relationship("TradeSignal", back_populates="orders")
