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
            # LangSmith Tracing이 .env 설정에 따라 자동 적용됨
        )
        
        # 회의록 요약 프롬프트 템플릿
        self.summary_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            당신은 전문 회의록 작성자입니다. 
            주어진 회의 전사 텍스트를 바탕으로 상세하고 구조화된 회의록을 작성해주세요.
            
            [작성 양식]
            # {title} 회의록
            
            ## 📅 요약
            (회의 전체 내용을 3줄로 요약)
            
            ## 📌 주요 안건
            (안건 1)
            (안건 2)
            ...
            
            ## 💬 상세 논의 내용
            (주제별로 나누어 상세히 기술)
            
            ## ✅ 결정 사항
            - (결정된 내용)
            
            ## 📝 향후 계획 / 액션 아이템
            - [ ] (작업 내용) (담당자)
            """),
            ("user", """
            [회의 제목]: {title}
            [전사 텍스트]:
            {transcript_text}
            
            위 내용을 바탕으로 회의록을 작성해주세요.
            """)
        ])
        
        self.chain = self.summary_prompt | self.llm | StrOutputParser()

    async def generate_summary(self, title: str, transcript_text: str) -> str:
        """
        회의 전사 텍스트를 입력받아 요약본 생성
        """
        try:
            if not transcript_text.strip():
                return "전사 데이터가 없어 요약할 수 없습니다."
                
            # LangChain 비동기 호출
            response = await self.chain.ainvoke({
                "title": title,
                "transcript_text": transcript_text
            })
            
            return response
            
        except Exception as e:
            print(f"LLM Generation Error: {str(e)}")
            return f"회의록 생성 중 오류가 발생했습니다: {str(e)}"

llm_service = LLMService()
