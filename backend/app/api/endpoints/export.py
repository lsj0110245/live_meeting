from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.api import deps
from app.db.session import get_db
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.models.user import User
import io
import pandas as pd
from datetime import datetime

router = APIRouter()

@router.get("/{meeting_id}", response_class=StreamingResponse)
def export_meeting(
    meeting_id: int,
    format: str = "csv",  # csv or xlsx
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    회의록 내보내기 (CSV / Excel)
    """
    # 1. 회의 권한 확인
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="회의를 찾을 수 없습니다.")
    if meeting.owner_id != current_user.id:
        raise HTTPException(status_code=400, detail="권한이 없습니다.")
        
    # 2. 데이터 조회 (전사 내용)
    transcripts = db.query(Transcript).filter(Transcript.meeting_id == meeting_id).order_by(Transcript.start_time).all()
    
    if not transcripts:
        raise HTTPException(status_code=404, detail="내보낼 전사 데이터가 없습니다.")
        
    # 3. 데이터프레임 생성
    data = []
    for t in transcripts:
        data.append({
            "Time": f"{t.start_time:.1f}s - {t.end_time:.1f}s",
            "Speaker": t.speaker or "Unknown",
            "Text": t.text
        })
    df = pd.DataFrame(data)
    
    # 4. 파일 생성 및 반환
    filename = f"meeting_{meeting_id}_{datetime.now().strftime('%Y%m%d')}"
    
    if format == "csv":
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename={filename}.csv"
        return response
        
    elif format == "xlsx":
        stream = io.BytesIO()
        df.to_excel(stream, index=False, engine='openpyxl')
        stream.seek(0)
        response = StreamingResponse(iter([stream.getvalue()]), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response.headers["Content-Disposition"] = f"attachment; filename={filename}.xlsx"
        return response
        
    else:
        raise HTTPException(status_code=400, detail="지원하지 않는 형식입니다. (csv, xlsx)")
