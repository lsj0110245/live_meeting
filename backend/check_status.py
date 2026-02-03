
import sys
sys.path.append('/app')
from app.db.session import SessionLocal
from app.models.meeting import Meeting
from app.models.user import User
from app.models.folder import Folder
from app.models.transcript import Transcript
from app.models.summary import Summary

def check_latest_meeting_status():
    db = SessionLocal()
    try:
        meeting = db.query(Meeting).order_by(Meeting.id.desc()).first()
        if meeting:
            print(f"Latest Meeting ID: {meeting.id}")
            print(f"Title: {meeting.title}")
            print(f"Status: {meeting.status}")
            print(f"Created At: {meeting.created_at}")
            
            # Summary Check
            summary = db.query(Summary).filter(Summary.meeting_id == meeting.id).first()
            if summary:
                print(f"Summary ID: {summary.id}")
                print(f"Summary Content Length: {len(summary.content)} chars")
            else:
                print("❌ Summary NOT FOUND for this meeting.")
                
            # Transcript Check
            transcripts = db.query(Transcript).filter(Transcript.meeting_id == meeting.id).all()
            print(f"Transcript Count: {len(transcripts)}")
        else:
            print("No meetings found.")
    finally:
        db.close()

if __name__ == "__main__":
    check_latest_meeting_status()
