from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# 데이터베이스 엔진 생성
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

# 세션 팩토리 생성
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# 의존성 주입용 DB 세션 생성
def get_db():
    """데이터베이스 세션 생성 및 종료"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
