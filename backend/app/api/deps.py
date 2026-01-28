from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import User as UserSchema

# OAuth2 스키마: 토큰 URL 설정
reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"/api/auth/login"
)

def get_current_user(
    db: Session = Depends(get_db),
    token: str = Depends(reusable_oauth2)
) -> User:
    """
    현재 로그인한 사용자 확인 (Dependency)
    JWT 토큰을 검증하고 사용자 객체를 반환합니다.
    """
    try:
        # JWT 토큰 디코딩
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = payload.get("sub")
        
        if token_data is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="인증 정보를 확인할 수 없습니다.",
            )
            
    except (JWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="인증 정보를 확인할 수 없습니다.",
        )
        
    # DB에서 사용자 조회
    user = db.query(User).filter(User.email == token_data).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="사용자를 찾을 수 없습니다.",
        )
        
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="비활성화된 사용자입니다.",
        )
        
    return user
