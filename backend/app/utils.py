from sqlalchemy.orm import Session
from app.models.meeting import Meeting

def get_unique_title(db: Session, title: str) -> str:
    """
    중복된 회의 제목이 있으면 _1, _2 등을 붙여 유니크한 제목 반환
    """
    if not title:
        return title
        
    base_title = title
    counter = 1
    
    # 정확히 일치하는 제목이 있는지 확인 (반복)
    # 효율성을 위해 LIKE 쿼리로 개선할 수도 있지만, 우선 단순 반복으로 구현
    while db.query(Meeting).filter(Meeting.title == title).first():
        title = f"{base_title}_{counter}"
        counter += 1
        
    return title

import os

def get_unique_filename(directory: str, filename: str) -> str:
    """
    해당 디렉토리에 동일한 파일명이 있으면 _1, _2 등을 붙여 유니크한 파일명 반환
    """
    base, ext = os.path.splitext(filename)
    counter = 1
    unique_filename = filename
    
    while os.path.exists(os.path.join(directory, unique_filename)):
        unique_filename = f"{base}_{counter}{ext}"
        counter += 1
        
    return unique_filename
