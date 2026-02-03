import json
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings

class LLMService:
    def __init__(self):
        # Local Llama 3 (Ollama) 초기화
        self.llm = ChatOllama(
            base_url=settings.LOCAL_LLM_URL,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            format="json",  # JSON 모드 강제
            num_ctx=8192    # 컨텍스트 윈도우 확장 (기본 2048 -> 8192)
        )
        
        # 회의록 요약 프롬프트 템플릿 (JSON 출력)
        self.summary_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            당신은 전문 회의록 작성 AI 비서입니다. 
            주어진 회의 전사 텍스트를 분석하여 구조화된 JSON 데이터로 반환해야 합니다.
            
            [분석 목표]
            1. 회의의 유형(meeting_type)을 추론하세요. (예: 주간보고, 아이디어 회의, 프로젝트 점검, 킥오프 등)
            2. 주요 안건에 맞는 적절한 회의 제목(title_suggestion)을 제안하세요.
            3. 참석자(attendees)를 대화 내용을 통해 식별하세요. (식별 불가 시 빈 문자열)
            4. 회의 내용을 상세히 요약하고 정리하세요.

            [출력 JSON 형식]
            {{
                "metadata": {{
                    "title_suggestion": "회의 제목 제안",
                    "meeting_type": "추론된 회의 유형",
                    "attendees": "참석자1, 참석자2" 
                }},
                "summary": {{
                    "purpose": "회의 목적 (1-2문장 요약)",
                    "content": "주요 안건 및 상세 논의 내용 (개조식으로 정리)",
                    "conclusion": "결론 및 결정 사항 (명확하게)",
                    "action_items": "향후 계획 및 액션 아이템 (담당자 포함)"
                }}
            }}
            
            **반드시 위 JSON 형식으로만 응답하세요.** (Markdown 코드 블록 없이 순수 JSON만 출력)
            """),
            ("user", """
            [기존 회의 제목]: {title}
            [전사 텍스트]:
            {transcript_text}
            """)
        ])
        
        self.chain = self.summary_prompt | self.llm | StrOutputParser()

    async def generate_summary(self, title: str, transcript_text: str) -> dict:
        """
        회의 전사 텍스트를 입력받아 구조화된 요약(JSON) 반환
        """
        try:
            if not transcript_text.strip():
                return None
                
            print("LLM 회의록 생성 시작...")
            
            # LangChain 비동기 호출
            response_text = await self.chain.ainvoke({
                "title": title,
                "transcript_text": transcript_text
            })
            
            print("LLM 회의록 생성 완료 (Raw):", response_text[:100] + "...")
            
            # JSON 파싱
            try:
                # 가끔 Markdown 코드 블록(```json ... ```)으로 감싸져 나오는 경우 처리
                cleaned_text = response_text.strip()
                if cleaned_text.startswith("```"):
                    import re
                    match = re.search(r"```(?:json)?(.*?)```", cleaned_text, re.DOTALL)
                    if match:
                        cleaned_text = match.group(1).strip()
                
                result_json = json.loads(cleaned_text)
                return result_json
                
            except json.JSONDecodeError as e:
                print(f"JSON Parsing Error: {e}")
                print(f"Failed Text: {response_text}")
                # 파싱 실패 시 기본 구조 반환
                return {
                    "metadata": {},
                    "summary": {
                        "purpose": "요약 실패",
                        "content": response_text, # 원본 텍스트라도 저장
                        "conclusion": "",
                        "action_items": ""
                    }
                }
            
        except Exception as e:
            print(f"LLM Generation Error: {str(e)}")
            return None

    async def generate_simple_summary(self, text: str) -> str:
        """
        단문 요약 생성 (중간 요약용) - 일반 텍스트 반환
        """
        try:
            # invoke uses the configured model (default format is json in __init__)
            # 임시로 format 해제는 불가하므로 JSON으로 유도 후 content 추출
            
            prompt = f"""
다음 회의 내용을 3줄 이내로 핵심만 요약해줘.
결과는 JSON 형식으로 반환해.
포맷: {{ "summary": "요약 내용..." }}

[회의 내용]
{text}
"""
            response = await self.llm.ainvoke(prompt)
            content = response.content
            
            import json
            try:
                data = json.loads(content)
                return data.get("summary", content)
            except:
                return content
                
        except Exception as e:
            print(f"Simple Summary Error: {str(e)}")
            return "요약 생성 실패"

llm_service = LLMService()
