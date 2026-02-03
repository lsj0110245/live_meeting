import json
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings

class LLMService:
    def __init__(self):
        # Local Llama 3 (Ollama) 초기화
        self.llm = ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            # format="json",  # 전역 JSON 모드는 가끔 행(Hang)을 유발하므로 해제
            num_ctx=8192,
            timeout=300.0
        )
        
        # 회의록 요약 프롬프트 템플릿 (JSON 출력) - Gemma 2 최적화
        self.summary_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            당신은 전문 회의록 작성 AI입니다. 입력된 회의 내용을 완벽하게 분석하여 구조화된 JSON 데이터로 변환해야 합니다.
            
            **필수 규칙:**
            1. **오직 순수 JSON만 출력하세요.** (Markdown ```json ... ``` 태그 사용 금지)
            2. 모든 내용은 **한국어(Korean)**로 작성하세요.
            3. 분석이 불가능한 항목은 빈 문자열("")로 두세요.
            
            **출력 JSON 포맷:**
            {{
                "metadata": {{
                    "title_suggestion": "회의 내용을 대표하는 구체적인 제목",
                    "meeting_type": "회의 유형 (예: 주간보고, 브레인스토밍, 킥오프, 코드리뷰)",
                    "attendees": "식별된 참석자 목록 (쉼표로 구분)" 
                }},
                "summary": {{
                    "purpose": "회의의 핵심 목적 (한 문장으로 명확히)",
                    "content": "주요 논의 사항 (개조식, 중요도 순 정렬)",
                    "conclusion": "최종 결론 및 합의 사항",
                    "action_items": "향후 계획 및 담당자별 액션 아이템"
                }}
            }}
            """),
            ("user", """
            [기존 제목]: {title}
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
            
            # [DEBUG] 원본 LLM 응답 로깅
            print(f"[DEBUG] Raw LLM Response (first 500 chars): {response_text[:500] if response_text else 'EMPTY'}")
            
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
                
                # [구조 보정] 만약 root에 purpose, content 등이 있다면 summary로 이동
                if "summary" not in result_json:
                    # 혹시 root에 바로 필드들이 있는지 확인
                    if "content" in result_json or "purpose" in result_json:
                        print("LLM returned flat JSON. Wrapping in 'summary'.")
                        result_json = {
                            "metadata": result_json.get("metadata", {}),
                            "summary": result_json
                        }
                
                return result_json
                
            except json.JSONDecodeError as e:
                print(f"JSON Parsing Error: {e}")
                print(f"Failed Text: {response_text}")
                # 파싱 실패 시 기본 구조 반환
                return {
                    "metadata": {},
                    "summary": {
                        "purpose": "요약 실패 (포맷 오류)",
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
            content = response.content.strip()
            
            # JSON 추출 시도
            try:
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(0))
                    return data.get("summary", content)
                return content
            except:
                return content
                
        except Exception as e:
            error_msg = f"요약 생성 실패: {str(e)}"
            print(f"Simple Summary Error: {str(e)}")
            return error_msg

llm_service = LLMService()
