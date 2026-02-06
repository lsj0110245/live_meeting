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
        full_text = "\n".join([f"{t.speaker}: {t.text}" for t in transcripts])
        
        # 2. LLM 요약 생성 (Llama 3.1 - 128k Context)
        print(f"회의록 생성 중... 회의 ID: {meeting_id}, 텍스트 길이: {len(full_text)}자")
        
        # [안전장치] 텍스트가 너무 길면 AI가 멈출 수 있으므로 10,000자 기준으로 분기
        # 10,000자 이하는 통째로, 그 이상은 청킹하여 처리
        SAFETY_LIMIT = 10000 
        
        if len(full_text) > SAFETY_LIMIT:
            print(f"[Safe Mode] 텍스트가 매우 깁니다({len(full_text)}자). 안전을 위해 Map-Reduce 전략 적용", flush=True)
            summary_data = await _generate_summary_with_chunking(meeting.title, full_text)
        else:
            # 긴 컨텍스트 모델 사용으로 청킹 없이 전체 처리 (정확도 최상)
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

        if not summ.get('content') or summ.get('purpose') == "내용 없음":
            # [Fallback] 요약이 비어있으면 원본 텍스트 일부를 넣어서 사용자에게 보여줌
            preview_text = full_text[:500] + "..." if len(full_text) > 500 else full_text
            summ['content'] = f"⚠️ 요약 내용이 생성되지 않았습니다. 원본 텍스트 미리보기:\n\n{preview_text}"
            summ['purpose'] = "요약 실패 (원문 표시 중)"

        # [Format Helper] JSON/Dict 형태의 문자열을 깔끔한 Markdown으로 변환
        def format_item(item):
            if not item: return "내용 없음"
            
            # 이미 문자열이고 JSON 포맷({, [)이 아니라면 그대로 반환
            if isinstance(item, str):
                item = item.strip()
                
                # Markdown Code Block 제거 (```json ... ```)
                if item.startswith('```'):
                    import re
                    # 첫 줄(```json)과 마지막 줄(```) 제거
                    item = re.sub(r'^```[a-zA-Z]*\n', '', item)
                    item = re.sub(r'\n```$', '', item)
                    item = item.strip()

                if not (item.startswith('{') or item.startswith('[')):
                    return item
                
                # JSON 문자열 파싱 시도 (ast -> json 순서)
                try:
                    import ast
                    # 1. Python Dictionary Style (Single Quotes)
                    item = ast.literal_eval(item)
                except:
                    try:
                        import json
                        # 2. Standard JSON Style (Double Quotes)
                        item = json.loads(item)
                    except:
                        return item # 파싱 실패 시 원본 반환

            # Dictionary 처리
            if isinstance(item, dict):
                lines = []
                for k, v in item.items():
                    # 키가 숫자인 경우(순서) 무시하거나 포맷팅
                    clean_key = k.lstrip('- ').strip()
                    lines.append(f"- **{clean_key}**: {v}")
                return "\n".join(lines)
            
            # Set 처리 (순서가 없으므로 정렬)
            if isinstance(item, set):
                # set을 리스트로 변환 및 정렬
                item = sorted(list(item), key=str)
                # 아래 List 처리 로직으로 흐르도록 하거나 직접 반환
                return "\n".join([f"- {str(x).strip()}" for x in item])

            # List 처리
            if isinstance(item, list):
                return "\n".join([f"- {str(x).strip()}" for x in item])
                
            return str(item)

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
        
        # 상태 업데이트 (completed)
        # 단순히 여기에서 completed로 바꾸면, upload.py의 흐름과 겹칠 수 있으나
        # upload.py는 이미 completed 상태에서 이 함수를 호출함.
        # 따라서 수동 호출(processing 상태)인 경우에만 유효함.
        if meeting.status in ["processing", "recording"]:
            meeting.status = "completed"
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
