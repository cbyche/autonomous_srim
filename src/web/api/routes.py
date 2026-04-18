from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.database import get_db
from src.database.repository import Repository
from src.srim.analyzer import analyze_stock
from src.config import load_config, get_config_value

router = APIRouter()

class WatchStockCreate(BaseModel):
    code: str
    name: str

@router.get("/portfolio")
def get_portfolio(db: Session = Depends(get_db)):
    repo = Repository(db)
    holdings = repo.get_all_holding_stages()
    return {"status": "success", "data": holdings}

@router.post("/watch-list")
def add_to_watch_list(item: WatchStockCreate, db: Session = Depends(get_db)):
    repo = Repository(db)
    config = load_config()
    required_ror = get_config_value(config, "trading", "required_ror_percent", default=8.0)
    
    # 추가 즉시 분석 수행
    srim_result = analyze_stock(item.code, item.name, "임시업종", "임시제품", required_ror)
    
    if srim_result:
        stock = repo.add_watch_stock(
            item.code, item.name, 
            buy_price=srim_result.buy_price,
            proper_price=srim_result.proper_price,
            sell_price=srim_result.sell_price,
            last_price=srim_result.last_price
        )
        return {"status": "success", "data": stock}
    else:
        # 데이터가 없어도 추가는 하지만 가격은 None
        stock = repo.add_watch_stock(item.code, item.name)
        return {"status": "warning", "message": "S-RIM 분석 실패. 종목은 추가됨.", "data": stock}

@router.delete("/watch-list/{code}")
def remove_from_watch_list(code: str, db: Session = Depends(get_db)):
    repo = Repository(db)
    success = repo.remove_watch_stock(code)
    if not success:
        raise HTTPException(status_code=404, detail="Stock not found in watch list")
    return {"status": "success"}

@router.get("/signals")
def get_signals(db: Session = Depends(get_db)):
    repo = Repository(db)
    signals = repo.get_pending_signals()
    return {"status": "success", "data": signals}
