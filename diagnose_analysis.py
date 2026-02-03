"""
백엔드 분석 상태 진단 스크립트
업로드 후 분석이 시작되지 않는 문제를 진단합니다.
"""
import sys
import os
sys.path.insert(0, 'c:/big20/live_meeting/backend')

from app.db.session import SessionLocal
from sqlalchemy import desc, text

db = SessionLocal()

print("=" * 80)
print("LiveMeeting 분석 상태 진단")
print("=" * 80)

try:
    # 1. 최근 회의 조회
    result = db.execute(text("""
        SELECT id, title, status, created_at, audio_file_path
        FROM meetings
        ORDER BY created_at DESC
        LIMIT 5
    """))
    
    meetings = result.fetchall()
    
    print("\n[1] 최근 회의 목록 (최신 5개)")
    print("-" * 80)
    for m in meetings:
        print(f"ID: {m[0]}")
        print(f"제목: {m[1]}")
        print(f"상태: {m[2]}")
        print(f"생성시간: {m[3]}")
        print(f"파일경로: {m[4]}")
        
        # 파일 존재 확인
        if m[4] and os.path.exists(m[4]):
            file_size = os.path.getsize(m[4]) / 1024 / 1024  # MB
            print(f"파일크기: {file_size:.2f} MB")
        else:
            print(f"⚠️ 파일 없음!")
        
        # 전사 레코드 확인
        transcript_result = db.execute(text("""
            SELECT COUNT(*), SUM(LENGTH(text))
            FROM transcripts
            WHERE meeting_id = :meeting_id
        """), {"meeting_id": m[0]})
        
        t_count, t_length = transcript_result.fetchone()
        print(f"전사 레코드: {t_count}개, 총 {t_length or 0}자")
        
        # 요약 확인
        summary_result = db.execute(text("""
            SELECT LENGTH(content)
            FROM summaries
            WHERE meeting_id = :meeting_id
        """), {"meeting_id": m[0]})
        
        s_row = summary_result.fetchone()
        if s_row and s_row[0]:
            print(f"요약: {s_row[0]}자")
        else:
            print(f"요약: 없음")
        
        print("-" * 80)
    
    # 2. Faster-Whisper 모델 확인
    print("\n[2] Faster-Whisper 모델 확인")
    print("-" * 80)
    try:
        from app.services.faster_whisper_stt_service import faster_whisper_stt_service
        print(f"✅ Faster-Whisper 서비스 임포트 성공")
        print(f"모델: {faster_whisper_stt_service.model_size}")
        print(f"디바이스: {faster_whisper_stt_service.device}")
    except Exception as e:
        print(f"❌ Faster-Whisper 서비스 오류: {e}")
    
    # 3. Ollama 모델 확인
    print("\n[3] Ollama LLM 모델 확인")
    print("-" * 80)
    try:
        from app.services.llm_service import llm_service
        print(f"✅ LLM 서비스 임포트 성공")
    except Exception as e:
        print(f"❌ LLM 서비스 오류: {e}")
    
    print("\n[4] 권장 조치")
    print("-" * 80)
    
    processing_count = sum(1 for m in meetings if m[2] == 'processing')
    if processing_count > 0:
        print(f"⚠️ {processing_count}개 회의가 'processing' 상태입니다.")
        print("   → 백엔드 터미널에서 오류 메시지 확인 필요")
        print("   → Faster-Whisper 모델이 설치되어 있는지 확인")
        print("   → GPU 메모리가 충분한지 확인")
    else:
        print("✅ 모든 회의가 처리 완료 상태입니다.")
    
finally:
    db.close()

print("\n" + "=" * 80)
print("진단 완료")
print("=" * 80)
