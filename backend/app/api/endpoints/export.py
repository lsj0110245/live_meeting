from typing import Any
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.api import deps
from app.db.session import get_db
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.models.summary import Summary
from app.models.user import User
import io
import pandas as pd
from datetime import datetime
import openpyxl
from urllib.parse import quote

router = APIRouter()


def parse_ai_summary(summary_content: str) -> dict:
    """
    AI 요약 내용을 파싱하여 회의 목적, 주요 내용, 결론 추출
    
    AI 요약 형식:
    ## 📅 요약
    ## 📌 주요 안건
    ## 💬 상세 논의 내용
    ## ✅ 결정 사항
    ## 📝 향후 계획 / 액션 아이템
    """
    result = {
        'purpose': '',
        'content': '',
        'conclusion': ''
    }
    
    try:
        # 섹션별로 추출
        # 요약 섹션 -> 회의 목적
        summary_match = re.search(r'##\s*📅\s*요약\s*\n(.*?)(?=##|$)', summary_content, re.DOTALL)
        if summary_match:
            result['purpose'] = summary_match.group(1).strip()
        
        # 주요 안건 + 상세 논의 내용 -> 주요 내용
        agenda_match = re.search(r'##\s*📌\s*주요 안건\s*\n(.*?)(?=##|$)', summary_content, re.DOTALL)
        discussion_match = re.search(r'##\s*💬\s*상세 논의 내용\s*\n(.*?)(?=##|$)', summary_content, re.DOTALL)
        
        content_parts = []
        if agenda_match:
            content_parts.append("【주요 안건】\n" + agenda_match.group(1).strip())
        if discussion_match:
            content_parts.append("【상세 논의】\n" + discussion_match.group(1).strip())
        
        result['content'] = '\n\n'.join(content_parts) if content_parts else summary_content[:500]
        
        # 결정 사항 + 향후 계획 -> 결론
        decision_match = re.search(r'##\s*✅\s*결정 사항\s*\n(.*?)(?=##|$)', summary_content, re.DOTALL)
        action_match = re.search(r'##\s*📝\s*향후 계획.*?\n(.*?)(?=##|$)', summary_content, re.DOTALL)
        
        conclusion_parts = []
        if decision_match:
            conclusion_parts.append("【결정 사항】\n" + decision_match.group(1).strip())
        if action_match:
            conclusion_parts.append("【향후 계획】\n" + action_match.group(1).strip())
        
        result['conclusion'] = '\n\n'.join(conclusion_parts) if conclusion_parts else ''
        
    except Exception as e:
        print(f"AI 요약 파싱 오류: {str(e)}")
        # 파싱 실패 시 전체 요약을 주요 내용에 넣기
        result['content'] = summary_content
    
    return result


@router.get("/{meeting_id}", response_class=StreamingResponse)
def export_meeting(
    meeting_id: int,
    format: str = "csv",  # csv or xlsx
    db: Session = Depends(get_db),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    회의록 내보내기 (CSV / Excel)
    - CSV: 전사 내용만 (한글 인코딩 수정)
    - Excel: source.xlsx 템플릿 기반 (메타데이터 + AI 요약)
    """
    # 1. 회의 권한 확인
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="회의를 찾을 수 없습니다.")
    if meeting.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="권한이 없습니다.")
        
    # 2. 데이터 조회
    transcripts = db.query(Transcript).filter(Transcript.meeting_id == meeting_id).order_by(Transcript.start_time).all()
    summary = db.query(Summary).filter(Summary.meeting_id == meeting_id).first()
    
    # 3. 파일 생성 및 반환
    filename = f"{meeting.title}_{datetime.now().strftime('%Y%m%d')}"
    
    if format == "csv":
        # CSV: Excel과 동일한 형식 (메타데이터 + AI 요약)
        # AI 요약 파싱
        parsed_summary = {'purpose': '', 'content': '', 'conclusion': ''}
        if summary:
            parsed_summary = parse_ai_summary(summary.content)
        
        # 데이터 구성
        data = [
            ["회의명", meeting.title or ''],
            ["회의 유형", meeting.meeting_type or ''],
            ["회의일시", meeting.meeting_date.strftime('%Y-%m-%d %H:%M') if meeting.meeting_date else ''],
            ["참석자", meeting.attendees or ''],
            ["작성자", meeting.writer or ''],
            ["회의 목적", parsed_summary['purpose']],
            ["주요 내용", parsed_summary['content']],
            ["결론 및 향후 계획", parsed_summary['conclusion']]
        ]
        
        df = pd.DataFrame(data, columns=["항목", "내용"])
        
        stream = io.StringIO()
        # 한글 인코딩 수정: utf-8-sig (BOM 추가)
        df.to_csv(stream, index=False, encoding='utf-8-sig')
        response = StreamingResponse(
            iter([stream.getvalue().encode('utf-8-sig')]), 
            media_type="text/csv; charset=utf-8"
        )
        encoded_filename = quote(filename)
        response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_filename}.csv"
        return response
        
    elif format == "xlsx":
        # Excel: 코드로 직접 생성 (템플릿 불필요)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "회의록"
        
        # AI 요약 파싱
        parsed_summary = {'purpose': '', 'content': '', 'conclusion': ''}
        if summary:
            parsed_summary = parse_ai_summary(summary.content)
        
        # 스타일 설정
        from openpyxl.styles import Font, Alignment, PatternFill
        
        header_font = Font(bold=True, size=12)
        header_fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
        
        # 데이터 입력 (A열: 레이블, B열: 값)
        rows_data = [
            ("회의명", meeting.title or ''),
            ("회의 유형", meeting.meeting_type or ''),
            ("회의일시", meeting.meeting_date.strftime('%Y-%m-%d %H:%M') if meeting.meeting_date else ''),
            ("참석자", meeting.attendees or ''),
            ("작성자", meeting.writer or ''),
            ("회의 목적", parsed_summary['purpose']),
            ("주요 내용", parsed_summary['content']),
            ("결론 및 향후 계획", parsed_summary['conclusion'])
        ]
        
        for idx, (label, value) in enumerate(rows_data, start=1):
            # A열: 레이블
            cell_a = ws.cell(row=idx, column=1, value=label)
            cell_a.font = header_font
            cell_a.fill = header_fill
            cell_a.alignment = Alignment(horizontal='left', vertical='top')
            
            # B열: 값
            cell_b = ws.cell(row=idx, column=2, value=value)
            cell_b.alignment = Alignment(horizontal='left', vertical='top', wrap_text=True)
        
        # 열 너비 조정
        ws.column_dimensions['A'].width = 20
        ws.column_dimensions['B'].width = 80
        
        # 행 높이 자동 조정 (내용이 긴 경우)
        for idx in range(6, 9):  # 회의 목적, 주요 내용, 결론 행
            ws.row_dimensions[idx].height = None  # 자동 높이
        
        # BytesIO로 저장
        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        
        response = StreamingResponse(
            iter([stream.getvalue()]), 
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        encoded_filename = quote(filename)
        response.headers["Content-Disposition"] = f"attachment; filename*=UTF-8''{encoded_filename}.xlsx"
        return response
        
    else:
        raise HTTPException(status_code=400, detail="지원하지 않는 형식입니다. (csv, xlsx)")
