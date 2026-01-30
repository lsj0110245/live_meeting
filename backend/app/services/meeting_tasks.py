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
        
        # 2. LLM 요약 생성
        print(f"회의록 생성 중... 회의 ID: {meeting_id}")
        summary_text = await llm_service.generate_summary(meeting.title, full_text)
        
        # 3. 요약 결과 저장 (Summary)
        # 이미 존재하는 요약이 있는지 확인
        existing_summary = db.query(Summary).filter(Summary.meeting_id == meeting_id).first()
        
        if existing_summary:
            existing_summary.content = summary_text
            # existing_summary.updated_at = func.now() # 모델에서 onupdate=func.now() 설정됨
            print(f"기존 요약 업데이트. 회의 ID: {meeting_id}")
        else:
            summary = Summary(
                meeting_id=meeting_id,
                content=summary_text,
                # key_points, action_items 등은 추후 JSON 파싱 구현 시 추가
            )
            db.add(summary)
            print(f"새 요약 생성. 회의 ID: {meeting_id}")
            
        db.commit()
        print(f"회의록 생성 완료. 회의 ID: {meeting_id}")
        
    except Exception as e:
        print(f"회의록 생성 실패. 회의 ID: {meeting_id}, 오류: {str(e)}")
    finally:
        db.close()
