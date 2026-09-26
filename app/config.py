from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    app_name:str='JobPilot AI'; environment:str='development'; debug:bool=True
    secret_key:str='change-me'; access_token_expire_minutes:int=1440
    database_url:str='sqlite:///./jobpilot.db'; redis_url:str='redis://localhost:6379/0'
    llm_provider:str='ollama'; ollama_base_url:str='http://localhost:11434'; ollama_model:str='llama3.2'
    openai_api_key:str|None=None; openai_model:str='gpt-5-mini'; storage_dir:str='./storage/resumes'
    cors_origins:str='http://localhost:5173'
    model_config=SettingsConfigDict(env_file='.env',extra='ignore')
    @property
    def cors_origin_list(self): return [x.strip() for x in self.cors_origins.split(',') if x.strip()]
@lru_cache
def get_settings(): return Settings()
settings=get_settings()
