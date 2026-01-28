from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api import deps
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserCreate, User as UserSchema

router = APIRouter()

@router.post("/register", response_model=UserSchema)
def register_user(
    *,
    db: Session = Depends(get_db),
    user_in: UserCreate,
) -> Any:
    """
    새로운 사용자 등록 (회원가입)
    """
    # 이메일 중복 확인
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="이미 존재하는 이메일입니다.",
        )

    # 사용자 생성
    user = User(
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        username=user_in.username or user_in.email.split("@")[0],
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login")
def login_access_token(
    db: Session = Depends(get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """
    OAuth2 호환 토큰 로그인 (JWT 발급)
    """
    # 사용자 인증
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="잘못된 이메일 또는 비밀번호입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="비활성화된 사용자입니다.")

    # 액세스 토큰 생성
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            user.email, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }


@router.post("/test-token", response_model=UserSchema)
def test_token(current_user: User = Depends(deps.get_current_user)) -> Any:
    """
    토큰 유효성 테스트 (현재 사용자 정보 반환)
    """
    return current_user
