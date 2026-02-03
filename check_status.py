import sys
sys.path.insert(0, 'c:/big20/live_meeting/backend')

from app.db.session import SessionLocal
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from sqlalchemy import desc

db = SessionLocal()

try:
    # 최근 회의 5개 조회
    recent_meetings = db.query(Meeting).order_by(desc(Meeting.created_at)).limit(5).all()
    
    print("=" * 80)
    print("최근 회의 목록 (최신 5개)")
    print("=" * 80)
    
    for meeting in recent_meetings:
        transcript_count = db.query(Transcript).filter(Transcript.meeting_id == meeting.id).count()
        
        print(f"\n회의 ID: {meeting.id}")
        print(f"제목: {meeting.title}")
        print(f"상태: {meeting.status}")
        print(f"생성 시간: {meeting.created_at}")
        print(f"전사 레코드 수: {transcript_count}")
        print(f"파일 경로: {meeting.audio_file_path}")
        print("-" * 80)
        
finally:
    db.close()
