from sqlalchemy.ext.declarative import declarative_base

# SQLAlchemy Base 모델
Base = declarative_base()

# 모든 모델을 여기에 import (Alembic autogenerate를 위해)
# from app.models.user import User
# from app.models.meeting import Meeting
# from app.models.transcript import Transcript
