import json
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings

class LLMService:
    def __init__(self):
        # Local EXAONE 3.5 (Ollama) 초기화
        self.llm = ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            # format="json",  # 전역 JSON 모드는 가끔 행(Hang)을 유발하므로 해제
            num_ctx=8192,
            timeout=300.0
        )
        
        # 회의록 요약 프롬프트 템플릿 (JSON 출력) - EXAONE 3.5 최적화
        self.summary_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            당신은 유능한 비즈니스 전문 비서입니다. 입력된 회의 내용을 정밀 분석하여 임원 보고용 품질의 회의록을 작성해야 합니다.

            **[작성 원칙]**
            1. **언어**: 내용은 반드시 완벽한 **한국어(Korean)**로 작성하십시오.
            2. **어조**: "합니다", "했음" 등의 명확하고 간결한 비즈니스 어조를 사용하십시오.
            3. **구조**: 반드시 아래 정의된 JSON 형식을 정확히 준수하십시오.
            4. **표현**: 
               - 리스트 아이템은 `-` (Dash) 불렛을 사용하여 가독성을 높이십시오.
               - 핵심 키워드나 숫자는 강조하십시오.

            **[출력 JSON 포맷]**
            (Key는 반드시 영어를 유지하고, Value는 한국어로 작성할 것)
            {{
                "metadata": {{
                    "title_suggestion": "회의의 핵심을 관통하는 간결한 제목 (예: '24년 3분기 API 성능 최적화 전략 회의')",
                    "meeting_type": "회의 성격 (예: 아이디어 회의, 주간 보고, 이슈 대응)",
                    "attendees": "참석자 명단 (식별 가능할 경우)" 
                }},
                "summary": {{
                    "purpose": "📅 **요약**\\n회의가 소집된 배경과 핵심 목적을 2~3문장으로 요약",
                    "content": "📌 **주요 안건 및 논의**\\n- 안건 1: 구체적인 논의 내용 및 쟁점\\n- 안건 2: 제안된 아이디어와 피드백",
                    "conclusion": "✅ **결론 및 결정 사항**\\n- 확정된 의사결정 사항\\n- 합의된 내용 (가장 중요)",
                    "action_items": "📝 **향후 계획**\\n- [담당자] 구체적인 실행 과제 및 마감 기한\\n- [공통] 다음 회의 일정 등"
                }}
            }}
            """),
            ("user", """
            [기존 제목]: {title}
            [전사 텍스트]:
            {transcript_text}

            위 내용을 바탕으로 전문적인 회의록 JSON을 생성해 주세요.
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
            다음 회의 내용을 **핵심만 요약하여 3줄 이내로** 작성해주세요.
            
            [원칙]
            1. 문장의 끝은 "함", "임" 등으로 간결하게 끝내세요.
            2. JSON 형식을 쓰지 말고, **순수한 텍스트**로 출력하세요.
            3. 불필요한 서두나 사족을 붙이지 마세요.

            [회의 내용]
            {text}
            """
            response = await self.llm.ainvoke(prompt)
            # EXAONE은 지시를 잘 따르므로 바로 텍스트 반환
            return response.content.strip()
                
        except Exception as e:
            error_msg = f"요약 생성 실패: {str(e)}"
            print(f"Simple Summary Error: {str(e)}")

    async def correct_transcript(self, text: str) -> str:
        """
        STT 전사 텍스트의 오타 및 문맥 보정 (하이브리드 전략 2단계)
        """
        try:
            prompt = f"""
            당신은 전문 교정 AI입니다. 아래 STT(음성 인식) 텍스트의 오타를 문맥에 맞게 수정하여 출력하십시오.

            **[교정 원칙]**
            1. **사실 유지**: 내용은 절대 변경하지 말고, 명백한 발음 오류만 수정하십시오.
            2. **용어 보정**: 
               - "에이아이" -> "AI", "쥐피티" -> "GPT", "도커" -> "Docker" 등 IT 전문 용어는 올바른 표기로 수정하십시오.
            3. **문맥 보정**:
               - "서버바" -> "서버가", "사억" -> "4억" 등 문법과 수치를 자연스럽게 다듬으십시오.
            4. **출력 형식**: 
               - 부연 설명 없이 **수정된 텍스트만** 출력하십시오.
               - 문장 맨 앞에 핵심 주제 키워드를 `[키워드]` 형태로 추가하십시오. (예: `[보안] OAuth 인증 이슈가...`)

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
