from sqlalchemy import text
import sys
import os

# Add parent directory to path to import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import engine

def add_columns():
    with engine.connect() as conn:
        print("Adding columns to meetings table...")
        try:
            conn.execute(text("ALTER TABLE meetings ADD COLUMN meeting_type VARCHAR"))
            print("Added meeting_type")
        except Exception as e:
            conn.rollback()
            print(f"meeting_type might already exist: {e}")

        try:
            conn.execute(text("ALTER TABLE meetings ADD COLUMN meeting_date TIMESTAMP"))
            print("Added meeting_date")
        except Exception as e:
            conn.rollback()
            # print(f"meeting_date failed (1st try): {e}")
            # try:
            #     conn.execute(text("ALTER TABLE meetings ADD COLUMN meeting_date TIMESTAMP"))
            #     print("Added meeting_date (TIMESTAMP)")
            # except Exception as e2:
            print(f"meeting_date might already exist: {e}")

        try:
            conn.execute(text("ALTER TABLE meetings ADD COLUMN attendees TEXT"))
            print("Added attendees")
        except Exception as e:
            conn.rollback()
            print(f"attendees might already exist: {e}")

        try:
            conn.execute(text("ALTER TABLE meetings ADD COLUMN writer VARCHAR"))
            print("Added writer")
        except Exception as e:
            conn.rollback()
            print(f"writer might already exist: {e}")
            
        conn.commit()
        print("Finished.")

if __name__ == "__main__":
    add_columns()
