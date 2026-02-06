
import sys
import asyncio
sys.path.append('/app')
from app.services.llm_service import llm_service

async def test_llm():
    print("Testing LLM Service...")
    title = "Test Meeting"
    text = "A: Hello, this is a test meeting. B: Yes, we are testing the LLM summary generation. A: Make sure checking the model availability. B: Okay, we will use llama3."
    
    try:
        result = await llm_service.generate_summary(title, text)
        if result:
            print("✅ LLM Summary Generated Successfully!")
            print(result)
        else:
            print("❌ LLM returned None.")
    except Exception as e:
        print(f"❌ Error during LLM testing: {e}")

if __name__ == "__main__":
    asyncio.run(test_llm())
