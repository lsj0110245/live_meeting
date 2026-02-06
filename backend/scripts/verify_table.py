from sqlalchemy import create_engine, inspect
import os

DATABASE_URL = "postgresql://lm_postgres:0000@localhost:15432/live_meeting"
engine = create_engine(DATABASE_URL)
inspector = inspect(engine)
tables = inspector.get_table_names()

print("Tables in DB:", tables)
if "intermediate_summaries" in tables:
    print("SUCCESS: intermediate_summaries table exists.")
else:
    print("FAILURE: intermediate_summaries table MISSING.")
