from app.db.session import SessionLocal
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.models.summary import Summary
from app.services.llm_service import llm_service

async def process_meeting_summary(meeting_id: int):
    """
    백그라운드 작업: 회의록 생성 및 저장
    """
    db = SessionLocal()
    try:
        # 1. 전사 데이터 조회
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        transcripts = db.query(Transcript).filter(Transcript.meeting_id == meeting_id).order_by(Transcript.start_time).all()
        
        if not transcripts:
            print(f"전사 데이터가 없습니다. 회의 ID: {meeting_id}")
            return

        # 전사 텍스트 합치기
        full_text = "\\n".join([f"{t.speaker}: {t.text}" for t in transcripts])
        
        # 2. LLM 요약 생성 (JSON 반환)
        print(f"회의록 생성 중... 회의 ID: {meeting_id}")
        summary_data = await llm_service.generate_summary(meeting.title, full_text)
        
        if not summary_data:
            print(f"LLM 응답 없음. 회의 ID: {meeting_id}")
            # 실패 시 기본 요약 생성 (사용자 알림용)
            summary_data = {
                "metadata": {},
                "summary": {
                    "purpose": "요약 생성 실패",
                    "content": "AI 서비스 응답이 없거나 타임아웃이 발생했습니다. 잠시 후 '회의록 생성' 버튼을 눌러 다시 시도해주세요.",
                    "conclusion": "",
                    "action_items": ""
                }
            }

        # 3. 메타데이터 업데이트 (비어있는 필드 채우기)
        metadata = summary_data.get("metadata", {})
        
        is_updated = False
        if not meeting.meeting_type and metadata.get("meeting_type"):
            meeting.meeting_type = metadata.get("meeting_type")
            is_updated = True
            
        if not meeting.attendees and metadata.get("attendees"):
            meeting.attendees = metadata.get("attendees")
            is_updated = True
            
        # 제목이 '제목 없음'이거나 비어있으면 제안된 제목 사용
        if (not meeting.title or meeting.title == "제목 없음") and metadata.get("title_suggestion"):
            from app.utils import get_unique_title
            suggested_title = metadata.get("title_suggestion")
            meeting.title = get_unique_title(db, suggested_title)
            is_updated = True
            
        if is_updated:
            db.add(meeting) # 세션에 추가 (이미 있지만 명시적 업데이트)
            print(f"메타데이터 자동 업데이트 완료. 회의 ID: {meeting_id}")

        # 4. 요약 결과 저장 (Summary) - Markdown 변환
        summ = summary_data.get("summary", {})
        
        markdown_content = f"""# {meeting.title} 회의록

## 📅 요약
{summ.get('purpose', '내용 없음')}

## 📌 주요 안건 및 내용
{summ.get('content', '내용 없음')}

## ✅ 결론 및 결정 사항
{summ.get('conclusion', '내용 없음')}

## 📝 향후 계획
{summ.get('action_items', '내용 없음')}
"""
        
        # 이미 존재하는 요약이 있는지 확인
        existing_summary = db.query(Summary).filter(Summary.meeting_id == meeting_id).first()
        
        if existing_summary:
            existing_summary.content = markdown_content
            # existing_summary.updated_at = func.now()
            print(f"기존 요약 업데이트. 회의 ID: {meeting_id}")
        else:
            summary = Summary(
                meeting_id=meeting_id,
                content=markdown_content,
            )
            db.add(summary)
            print(f"새 요약 생성. 회의 ID: {meeting_id}")
            
        db.commit()
        print(f"회의록 생성 완료. 회의 ID: {meeting_id}")
        
    except Exception as e:
        print(f"회의록 생성 실패. 회의 ID: {meeting_id}, 오류: {str(e)}")
    finally:
        db.close()
