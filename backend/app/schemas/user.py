from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

# 공통 속성 (Base)
class UserBase(BaseModel):
    email: EmailStr
    username: str | None = Field(None, max_length=10)
    is_active: bool | None = True

# 회원가입 시 받을 데이터 (Create)
class UserCreate(UserBase):
    password: str = Field(..., min_length=4)

# 업데이트 시 받을 데이터 (Update)
class UserUpdate(BaseModel):
    email: EmailStr | None = None
    username: str | None = None
    password: str | None = None
    is_active: bool | None = None

# DB에서 조회된 데이터 (Response)
# 비밀번호는 포함하지 않음
class User(UserBase):
    id: int
    created_at: datetime | None = None

    class Config:
        from_attributes = True
