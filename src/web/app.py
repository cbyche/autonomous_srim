from fastapi import FastAPI, Depends, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from src.database import get_db, init_db
from src.database.repository import Repository
from src.web.api.routes import router as api_router

import os

# DB 초기화
init_db()

app = FastAPI(title="Autonomous S-RIM Dashboard", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 및 템플릿 마운트
base_dir = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(base_dir, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

# API 라우터 등록
app.include_router(api_router, prefix="/api")

@app.get("/")
async def read_dashboard(request: Request, db: Session = Depends(get_db)):
    """대시보드 메인 페이지 렌더링"""
    repo = Repository(db)
    
    # 기본 데이터 조회
    holdings = repo.get_all_holding_stages()
    watch_list = repo.get_watch_stocks()
    signals = repo.get_pending_signals()
    orders = repo.get_recent_orders(limit=10)
    
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request, 
            "holdings": holdings,
            "watch_list": watch_list,
            "signals": signals,
            "orders": orders
        }
    )
