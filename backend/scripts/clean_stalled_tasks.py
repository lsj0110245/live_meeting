import sys
import os
import shutil

# 프로젝트 루트 경로를 sys.path에 추가 (backend 폴더 기준)
sys.path.insert(0, '/app')

from app.db.session import SessionLocal
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.models.summary import Summary

def clean_stalled_tasks():
    db = SessionLocal()
    try:
        # 삭제 대상 상태: processing, error, uploaded (아직 STT 전)
        target_statuses = ['processing', 'error', 'uploaded']
        meetings = db.query(Meeting).filter(Meeting.status.in_(target_statuses)).all()
        
        print(f"총 {len(meetings)}개의 진행 중/오류 회의를 발견했습니다.")
        
        for meeting in meetings:
            print(f"\n[삭제 중] Meeting ID: {meeting.id}, Title: {meeting.title}, Status: {meeting.status}")
            
            # 1. 관련 파일 삭제
            if meeting.audio_file_path and os.path.exists(meeting.audio_file_path):
                try:
                    os.remove(meeting.audio_file_path)
                    print(f"  - 오디오 파일 삭제 완료: {meeting.audio_file_path}")
                except Exception as e:
                    print(f"  - 오디오 파일 삭제 실패: {str(e)}")
            else:
                print(f"  - 오디오 파일 없음 (pass): {meeting.audio_file_path}")
            
            # 2. 관련 데이터 삭제 (Cascade 설정되어 있으면 자동이지만, 명시적으로 삭제)
            db.query(Transcript).filter(Transcript.meeting_id == meeting.id).delete()
            db.query(Summary).filter(Summary.meeting_id == meeting.id).delete()
            
            # 3. 회의 레코드 삭제
            db.delete(meeting)
            print("  - DB 레코드 삭제 완료")
            
        db.commit()
        print("\n모든 작업이 완료되었습니다.")
        
    except Exception as e:
        db.rollback()
        print(f"오류 발생: {str(e)}")
    finally:
        db.close()

if __name__ == "__main__":
    clean_stalled_tasks()
