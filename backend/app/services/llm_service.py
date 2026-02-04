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
            4. **리스트 형태 표기 금지**: `['내용']`과 같은 형식은 절대 사용하지 마세요. 대신 `-`를 사용한 Markdown 불렛 포인트를 사용하세요.
            
            **출력 JSON 포맷:**
            {{
                "metadata": {{
                    "title_suggestion": "회의 내용을 대표하는 구체적인 제목",
                    "meeting_type": "회의 유형 (예: 주간보고, 브레인스토밍, 킥오프, 코드리뷰)",
                    "attendees": "식별된 참석자 목록 (쉼표로 구분)" 
                }},
                "summary": {{
                    "purpose": "📅 **요약**\\n회의의 핵심 목적 및 개요",
                    "content": "📌 **주요 안건 및 내용**\\n- 안건 1\\n- 안건 2 (심층 분석 내용)",
                    "conclusion": "✅ **결론 및 결정 사항**\\n- 확정된 내용...\\n- 합의된 사항...",
                    "action_items": "📝 **향후 계획**\\n- [담당자] 할 일 1\\n- [담당자] 할 일 2"
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

    async def correct_transcript(self, text: str) -> str:
        """
        STT 전사 텍스트의 오타 및 문맥 보정 (하이브리드 전략 2단계)
        """
        try:
            prompt = f"""
            당신은 전문 교정/윤문 AI입니다. 아래 텍스트는 음성 인식(STT) 결과물입니다. 발음이 비슷하여 잘못 인식된 단어나 문맥상 어색한 표현을 **원래 의미를 훼손하지 않는 선에서** 교정해주세요.

            **교정 원칙:**
            1. **사실 왜곡 금지**: 없는 내용을 지어내거나(Hallucination), 핵심 키워드를 함부로 바꾸지 마세요.
            2. **문맥 기반 오타 수정**: "서버바 죽었다" -> "서버가 죽었다" 같이 명백한 오타만 수정하세요.
            3. **전문 용어 보정**: "기터브", "파이썬" 등은 "GitHub", "Python" 처럼 정확한 영문/한글 표기로 고치세요.
            4. **결과만 출력**: 설명이나 부연 없이 **교정된 텍스트만** 출력하세요. (JSON 사용 금지)

            [원본 텍스트]:
            {text}
            """
            
            # JSON 모드 해제 (단순 텍스트 출력을 위해)
            # 현재 self.llm 인스턴스는 JSON 출력을 선호할 수 있으므로, 
            # 단순히 invoke 호출하되, 프롬프트에서 결과만 출력하도록 강력히 지시
            
            response = await self.llm.ainvoke(prompt)
            corrected_text = response.content.strip()
            
            # 혹시라도 JSON이나 마크다운으로 감싸져 있으면 제거
            if corrected_text.startswith('"') and corrected_text.endswith('"'):
                corrected_text = corrected_text[1:-1]
            
            return corrected_text
            
        except Exception as e:
            print(f"Transcript Correction Error: {str(e)}")
            return text # 실패 시 원본 그대로 반환

llm_service = LLMService()
