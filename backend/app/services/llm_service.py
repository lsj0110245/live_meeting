import json
from langchain_community.chat_models import ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.core.config import settings
import re
import asyncio  # [FIX] asyncio import 추가

class LLMService:
    def __init__(self):
        # Local EXAONE 3.5 (Ollama) 초기화
        self.llm = ChatOllama(
            base_url=settings.OLLAMA_BASE_URL,
            model=settings.LLM_MODEL,
            temperature=settings.LLM_TEMPERATURE,
            # format="json",  # 전역 JSON 모드는 가끔 행(Hang)을 유발하므로 해제
            num_ctx=16384,
            timeout=600.0
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
            
            # LangChain 비동기 호출 (실제로는 내부에 Blocking I/O가 있으므로 스레드 풀에서 실행)
            # asyncio.to_thread로 감싸서 이벤트 루프 차단 방지
            import asyncio
            response_text = await asyncio.to_thread(
                lambda: self.chain.invoke({
                    "title": title,
                    "transcript_text": transcript_text
                })
            )
            
            # [DEBUG] 원본 LLM 응답 로깅
            print(f"[DEBUG] Raw LLM Response (first 500 chars): {response_text[:500] if response_text else 'EMPTY'}")
            
            # JSON 파싱 및 보정
            try:
                # [전처리] Markdown Code Block 제거 (```json ... ```) 및 불필요한 공백 제거
                clean_text = response_text.strip()
                if "```" in clean_text:
                    import re
                    clean_text = re.sub(r'^```[a-zA-Z]*\n', '', clean_text)
                    clean_text = re.sub(r'\n```$', '', clean_text)
                    clean_text = clean_text.strip()
                
                result_json = null = None # 파싱 결과 초기화

                # 1차 시도: 표준 JSON 파싱
                try:
                    result_json = json.loads(clean_text)
                except json.JSONDecodeError:
                    # 2차 시도: Python AST (Single Quote 허용)
                    try:
                        import ast
                        result_json = ast.literal_eval(clean_text)
                    except:
                        # 3차 시도: 텍스트 내에서 JSON 객체 부분만 추출 ('{' 로 시작해서 '}' 로 끝나는 구간)
                        try:
                            start_idx = clean_text.find('{')
                            end_idx = clean_text.rfind('}')
                            if start_idx != -1 and end_idx != -1:
                                json_part = clean_text[start_idx:end_idx+1]
                                result_json = json.loads(json_part)
                            else:
                                raise ValueError("No JSON object found")
                        except:
                            raise ValueError("All parsing attempts failed")

                # [구조 보정] 만약 root에 purpose, content 등이 있다면 summary로 이동
                if isinstance(result_json, dict):
                    if "summary" not in result_json:
                        if "content" in result_json or "purpose" in result_json:
                            print("LLM returned flat JSON. Wrapping in 'summary'.")
                            result_json = {
                                "metadata": result_json.get("metadata", {}),
                                "summary": result_json
                            }
                
                return result_json
                
            except Exception as e:
                print(f"JSON Parsing Error: {e}")
                print(f"Failed Text: {response_text}")
                
                # 파싱 실패 시 기본 구조 반환 (전체 텍스트 오염 방지)
                fallback_content = f"⚠️ 데이터 형식을 해석할 수 없습니다. 원본 텍스트:\n\n{response_text}"
                try:
                    # 너무 길면 잘라서 보여줌
                    if len(response_text) > 1000:
                         fallback_content = f"⚠️ 데이터 형식을 해석할 수 없습니다. 원본 텍스트(일부):\n\n{response_text[:1000]}..."
                except:
                    pass

                return {
                    "metadata": {},
                    "summary": {
                        "purpose": "요약 실패 (포맷 오류)",
                        "content": fallback_content,
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
            response = await asyncio.to_thread(
                lambda: self.llm.invoke(prompt)
            )
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
            if not text or len(text.strip()) <= 1:
                return text

            if "마이크" in text and "테스트" in text and len(text) < 20:
                return ""

            prompt = f"""
            당신은 STT 텍스트 교정기입니다. 다음 텍스트의 오타만 수정하세요.
            설명, 인사, 사족은 절대 금지합니다. 오직 교정된 결과만 출력하세요.
            내용이 없거나 무의미하면 공백을 출력하세요.

            [원본]: {text}
            """
            
            response = await asyncio.to_thread(
                lambda: self.llm.invoke(prompt)
            )
            corrected_text = response.content.strip()
            
            # 사족 패턴 제거 (설명조 문구가 포함되면 원본 유지 또는 버림)
            stop_words = ["제공해 주시면", "수정할 내용이", "어렵습니다", "정보가 필요", "출력하지 않습니다", "추가 정보", "원본 텍스트"]
            if any(word in corrected_text for word in stop_words):
                # 만약 주제 키워드만 있고 나머지가 설명이면 비움
                if len(corrected_text) < 50: 
                    return "" 
                return text
            
            # [없음] 이나 빈 대괄호 제거
            corrected_text = corrected_text.replace("[없음]", "").replace("[]", "").strip()
            
            if not corrected_text:
                return ""
            
            # 혹시라도 JSON이나 마크다운으로 감싸져 있으면 제거
            if corrected_text.startswith('"') and corrected_text.endswith('"'):
                corrected_text = corrected_text[1:-1]
            
            return corrected_text
            
        except Exception as e:
            print(f"Transcript Correction Error: {str(e)}")
            return text # 실패 시 원본 그대로 반환

llm_service = LLMService()
