from fastapi import APIRouter, Depends, HTTPException, Request
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
            item.code, item.name, srim_result.industry, srim_result.product,
            buy_target_price=srim_result.buy_target_price,
            sell_target_1=srim_result.sell_target_1,
            sell_target_2=srim_result.sell_target_2,
            sell_target_3=srim_result.sell_target_3,
            sell_target_4=srim_result.sell_target_4,
            roe=srim_result.roe, buy_yield=srim_result.buy_yield
        )
        return {"status": "success", "data": stock}
    else:
        raise HTTPException(status_code=400, detail="S-RIM 분석 실패. 종목을 추가할 수 없습니다.")

@router.post("/settings/reload-scheduler")
def reload_scheduler(request: Request):
    """설정 파일을 다시 읽고 스케줄러를 재시작한다."""
    config = load_config()
    
    # app.state에 저장된 스케줄러 참조
    scheduler_mgr = getattr(request.app.state, 'scheduler', None)
    if scheduler_mgr:
        scheduler_mgr.update_config_and_reload(config)
        return {"status": "success", "message": "스케줄러 설정이 재적용되었습니다."}
    else:
        raise HTTPException(status_code=500, detail="스케줄러 인스턴스를 찾을 수 없습니다.")

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
