from app.db.session import SessionLocal
from app.models.meeting import Meeting
from app.models.transcript import Transcript
from app.models.summary import Summary
from app.services.llm_service import llm_service
from app.models.enums import MeetingStatus

from app.services.progress_service import progress_service

async def process_meeting_summary(meeting_id: int):
    """
    백그라운드 작업: 회의록 생성 및 저장
    """
    db = SessionLocal()
    try:
        progress_service.set_progress(meeting_id, 10) # [Progress] 시작

        # 1. 전사 데이터 조회
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        transcripts = db.query(Transcript).filter(Transcript.meeting_id == meeting_id).order_by(Transcript.start_time).all()
        
        if not transcripts:
            print(f"전사 데이터가 없습니다. 회의 ID: {meeting_id}")
            progress_service.set_progress(meeting_id, 100) # 데이터 없음 = 완료 처리
            return

        progress_service.set_progress(meeting_id, 20) # [Progress] 데이터 로드 완료

        # 전사 텍스트 합치기
        full_text = "\n".join([f"{t.speaker}: {t.text}" for t in transcripts])
        
        # 2. LLM 요약 생성 (Llama 3.1 - 128k Context)
        print(f"회의록 생성 중... 회의 ID: {meeting_id}, 텍스트 길이: {len(full_text)}자")
        progress_service.set_progress(meeting_id, 30) # [Progress] 요약 생성 시작
        
        # [New] 긴 작업을 위해 진행률을 서서히 올리는 내부 태스크
        import asyncio
        stop_climb = asyncio.Event()
        async def slow_climb():
            p = 31
            while not stop_climb.is_set() and p < 90:
                await asyncio.sleep(2) # 2초마다 1%씩 상승
                if not stop_climb.is_set():
                    progress_service.set_progress(meeting_id, p)
                    p += 1
        
        climb_task = asyncio.create_task(slow_climb())
        
        try:
            # [안전장치] 텍스트가 너무 길면 AI가 멈출 수 있으므로 10,000자 기준으로 분기
            SAFETY_LIMIT = 10000 
            if len(full_text) > SAFETY_LIMIT:
                print(f"[Safe Mode] 텍스트가 매우 깁니다({len(full_text)}자). 안전을 위해 Map-Reduce 전략 적용", flush=True)
                summary_data = await _generate_summary_with_chunking(meeting.title, full_text)
            else:
                summary_data = await llm_service.generate_summary(meeting.title, full_text)
        finally:
            stop_climb.set()
            await climb_task # 클라이밍 태스크 종료 대기
        
        progress_service.set_progress(meeting_id, 90) # [Progress] 요약 생성 완료 (거의 끝남)

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

        progress_service.set_progress(meeting_id, 95) # [Progress] 메타데이터 처리 완료

        # 4. 요약 결과 저장 (Summary) - Markdown 변환
        summ = summary_data.get("summary", {})

        if not summ.get('content') or summ.get('purpose') == "내용 없음":
            # [Fallback] 요약이 비어있으면 원본 텍스트 일부를 넣어서 사용자에게 보여줌
            preview_text = full_text[:500] + "..." if len(full_text) > 500 else full_text
            summ['content'] = f"⚠️ 요약 내용이 생성되지 않았습니다. 원본 텍스트 미리보기:\n\n{preview_text}"
            summ['purpose'] = "요약 실패 (원문 표시 중)"

        # [Format Helper] JSON/Dict 형태의 문자열을 깔끔한 Markdown으로 변환
        def format_item(item):
            if not item: return "내용 없음"
            
            # 이미 문자열이고 JSON 포맷({, [)이 아이템 자체가 문자열인 경우
            if isinstance(item, str):
                item = item.strip()
                
                # Markdown Code Block 제거 (```json ... ```)
                if item.startswith('```'):
                    import re
                    item = re.sub(r'^```[a-zA-Z]*\n', '', item)
                    item = re.sub(r'\n```$', '', item)
                    item = item.strip()

                if not (item.startswith('{') or item.startswith('[')):
                    return item
                
                # JSON 문자열 파싱 시도
                try:
                    import ast
                    item = ast.literal_eval(item)
                except:
                    try:
                        import json
                        item = json.loads(item)
                    except:
                        return item # 파싱 실패 시 원본 반환

            # 재귀적 포맷팅 함수 정의
            def recursive_format(val, level=0):
                indent = "  " * level
                if isinstance(val, dict):
                    lines = []
                    for k, v in val.items():
                        clean_key = k.lstrip('- ').strip()
                        # 키가 의미 있는 내용이면 볼드 처리, 아니면 값만 표시
                        if isinstance(v, (dict, list)):
                            lines.append(f"{indent}- **{clean_key}**")
                            lines.append(recursive_format(v, level + 1))
                        else:
                            lines.append(f"{indent}- **{clean_key}**: {str(v)}")
                    return "\n".join(lines)
                
                elif isinstance(val, list) or isinstance(val, set):
                    lines = []
                    for x in val:
                        # 리스트 내부 아이템이 문자열이면 단순 불렛, 복잡하면 재귀
                        if isinstance(x, str):
                            lines.append(f"{indent}- {x}")
                        else:
                            lines.append(recursive_format(x, level))
                    return "\n".join(lines)
                
                else:
                    return f"{indent}{str(val)}"

            return recursive_format(item)

        markdown_content = f"""# {meeting.title} 회의록

## 📅 요약
{format_item(summ.get('purpose', '내용 없음'))}

## 📌 주요 안건 및 내용
{format_item(summ.get('content', '내용 없음'))}

## ✅ 결론 및 결정 사항
{format_item(summ.get('conclusion', '내용 없음'))}

## 📝 향후 계획
{format_item(summ.get('action_items', '내용 없음'))}
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
        
        progress_service.set_progress(meeting_id, 100) # [Progress] 저장 완료 (최종 완료)

        # 상태 업데이트 (completed)
        # 단순히 여기에서 completed로 바꾸면, upload.py의 흐름과 겹칠 수 있으나
        # upload.py는 이미 completed 상태에서 이 함수를 호출함.
        # 따라서 수동 호출(processing 상태)인 경우에만 유효함.
        if meeting.status in [MeetingStatus.PROCESSING, MeetingStatus.RECORDING]:
            meeting.status = MeetingStatus.COMPLETED
            db.commit()
        
    except Exception as e:
        print(f"회의록 생성 실패. 회의 ID: {meeting_id}, 오류: {str(e)}")
    finally:
        db.close()


async def _generate_summary_with_chunking(title: str, full_text: str) -> dict:
    """
    긴 텍스트를 청킹하여 Map-Reduce 방식으로 요약 생성
    """
    
    # 청킹 설정
    CHUNK_SIZE = 3000  # 3000자 청크
    OVERLAP = 500      # 500자 오버랩
    
    # 텍스트 청킹
    chunks = []
    start = 0
    while start < len(full_text):
        end = start + CHUNK_SIZE
        chunks.append(full_text[start:end])
        start += (CHUNK_SIZE - OVERLAP)
    
    print(f"  총 {len(chunks)}개 청크로 분할")
    
    # Step 1: Map - 각 청크 요약
    partial_summaries = []
    for i, chunk in enumerate(chunks):
        print(f"  청크 {i+1}/{len(chunks)} 요약 중...")
        summary_text = await llm_service.generate_simple_summary(chunk)
        if summary_text:
            partial_summaries.append(summary_text)
    
    # Step 2: Reduce - 통합 요약
    combined_text = "\n\n".join(partial_summaries)
    print(f"  부분 요약 통합 중... (총 {len(combined_text)}자)")
    
    final_summary = await llm_service.generate_summary(title, combined_text)
    return final_summary
