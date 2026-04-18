import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.database.models import Base
from src.config import load_config, get_config_value

# 설정 로드
config = load_config()
db_url = get_config_value(config, "database", "url", default="sqlite:///data/autonomous_srim.db")

# sqlite:///data/... 형식인 경우 data 디렉토리 생성
if db_url.startswith("sqlite:///"):
    db_path = db_url.replace("sqlite:///", "")
    db_dir = Path(db_path).parent
    if str(db_dir) != "." and str(db_dir) != "":
        db_dir.mkdir(parents=True, exist_ok=True)

# 엔진 및 세션 팩토리 생성
engine = create_engine(
    db_url, connect_args={"check_same_thread": False} if db_url.startswith("sqlite") else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """데이터베이스 테이블 생성"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """FastAPI Depends용 세션 제너레이터"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
