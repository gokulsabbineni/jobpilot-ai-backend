from app.config import settings
def get_llm_provider():
 if settings.llm_provider=='ollama':
  from app.ai.providers.ollama import OllamaProvider; return OllamaProvider()
 from app.ai.providers.openai_provider import OpenAIProvider; return OpenAIProvider()
