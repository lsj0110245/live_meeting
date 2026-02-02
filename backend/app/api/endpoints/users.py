from typing import Any
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserUpdate, User as UserSchema
import shutil
import os
import uuid

router = APIRouter()

@router.get("/me", response_model=UserSchema)
def read_user_me(
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    내 프로필 정보 조회
    """
    return current_user

@router.put("/me", response_model=UserSchema)
def update_user_me(
    *,
    db: Session = Depends(get_db),
    user_in: UserUpdate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    내 프로필 정보 수정
    """
    if user_in.email and user_in.email != current_user.email:
        # 이메일 중복 확인
        existing_user = db.query(User).filter(User.email == user_in.email).first()
        if existing_user:
            raise HTTPException(status_code=400, detail="이미 사용 중인 이메일입니다.")
        current_user.email = user_in.email

    if user_in.username is not None:
        current_user.username = user_in.username
    if user_in.age is not None:
        current_user.age = user_in.age
    if user_in.phone_number is not None:
        current_user.phone_number = user_in.phone_number
    if user_in.team_name is not None:
        current_user.team_name = user_in.team_name
    
    # 비밀번호 변경 로직은 별도로 분리하거나 여기서 처리 가능 (현재는 생략 또는 포함 가능)
    # 안전을 위해 비밀번호 변경은 별도 API 권장하나, 여기서는 UserUpdate에 password가 있으므로 로직 추가 가능
    # (일단 프로필 정보 위주로 구현)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/me/image", response_model=UserSchema)
async def upload_profile_image(
    *,
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    프로필 이미지 업로드
    """
    # Allowed extensions
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
    
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="지원하지 않는 이미지 형식입니다.")

    # 저장 디렉토리
    upload_dir = "media/profiles"
    os.makedirs(upload_dir, exist_ok=True)
    
    # 파일명 생성 (UUID)
    filename = f"{uuid.uuid4()}.{ext}"
    file_path = os.path.join(upload_dir, filename)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 기존 이미지 삭제 (선택 사항)
        if current_user.profile_image_path and os.path.exists(current_user.profile_image_path):
            try:
                # 기본 이미지가 아니면 삭제 로직 등 필요할 수 있음
                os.remove(current_user.profile_image_path)
            except:
                pass
                
        # DB 업데이트
        current_user.profile_image_path = file_path
        db.add(current_user)
        db.commit()
        db.refresh(current_user)
        
        return current_user
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"이미지 저장 실패: {str(e)}")
