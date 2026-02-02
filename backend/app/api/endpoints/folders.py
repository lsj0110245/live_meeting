from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.folder import Folder
from app.models.meeting import Meeting
from app.models.user import User
from app.schemas.folder import FolderCreate, FolderUpdate, Folder as FolderSchema

router = APIRouter()

@router.post("/", response_model=FolderSchema)
def create_folder(
    *,
    db: Session = Depends(get_db),
    folder_in: FolderCreate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    새 폴더 생성
    """
    folder = Folder(name=folder_in.name, owner_id=current_user.id)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder

@router.get("/", response_model=List[FolderSchema])
def read_folders(
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    폴더 목록 조회
    """
    folders = (
        db.query(Folder)
        .filter(Folder.owner_id == current_user.id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return folders

@router.put("/{folder_id}", response_model=FolderSchema)
def update_folder(
    *,
    db: Session = Depends(get_db),
    folder_id: int,
    folder_in: FolderUpdate,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    폴더 이름 수정
    """
    folder = db.query(Folder).filter(Folder.id == folder_id, Folder.owner_id == current_user.id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다.")
    
    folder.name = folder_in.name
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder

@router.delete("/{folder_id}")
def delete_folder(
    *,
    db: Session = Depends(get_db),
    folder_id: int,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    폴더 삭제 (폴더 내 회의는 '미분류'로 이동 - folder_id = None)
    """
    folder = db.query(Folder).filter(Folder.id == folder_id, Folder.owner_id == current_user.id).first()
    if not folder:
        raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다.")
    
    # 폴더 내 회의들의 folder_id를 Null로 설정 (안전한 삭제)
    meetings = db.query(Meeting).filter(Meeting.folder_id == folder_id).all()
    for meeting in meetings:
        meeting.folder_id = None
        db.add(meeting)
    
    db.delete(folder)
    db.commit()
    return {"status": "success"}

@router.put("/{folder_id}/meetings/{meeting_id}")
def move_meeting_to_folder(
    *,
    db: Session = Depends(get_db),
    folder_id: int,
    meeting_id: int,
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    회의를 특정 폴더로 이동 (folder_id가 0이면 미분류로 이동)
    """
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id, Meeting.owner_id == current_user.id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="회의를 찾을 수 없습니다.")
    
    if folder_id == 0:
        # 미분류로 이동
        meeting.folder_id = None
    else:
        # 폴더 존재 확인
        folder = db.query(Folder).filter(Folder.id == folder_id, Folder.owner_id == current_user.id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다.")
        meeting.folder_id = folder_id
        
    db.add(meeting)
    db.commit()
    return {"status": "success"}

@router.put("/{folder_id}/meetings")
def bulk_move_meetings_to_folder(
    *,
    db: Session = Depends(get_db),
    folder_id: int,
    meeting_ids: List[int],
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    여러 회의를 특정 폴더로 이동 (folder_id가 0이면 미분류로 이동)
    """
    if folder_id != 0:
        # 폴더 존재 확인
        folder = db.query(Folder).filter(Folder.id == folder_id, Folder.owner_id == current_user.id).first()
        if not folder:
            raise HTTPException(status_code=404, detail="폴더를 찾을 수 없습니다.")
    
    # 회의들 조회 및 업데이트
    meetings = db.query(Meeting).filter(Meeting.id.in_(meeting_ids), Meeting.owner_id == current_user.id).all()
    
    for meeting in meetings:
        if folder_id == 0:
            meeting.folder_id = None
        else:
            meeting.folder_id = folder_id
        db.add(meeting)
    
    db.commit()
    return {"status": "success", "updated_count": len(meetings)}
