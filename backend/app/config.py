from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://inquix:inquix@localhost:5432/inquix"
    ollama_url: str = "http://localhost:11434"
    redis_url: str = "redis://localhost:6379/0"
    redis_user_key: str = ""
    redis_account_key: str = ""

    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5:3b"
    groq_api_key: str = ""

    gemini_api_key: str = ""
    openai_api_key: str = ""
    firecrawler_api_key: str = ""

    embed_provider: str = "ollama"
    embedding_model: str = "nomic-embed-text"
    jina_api_key: str = ""

    vision_model: str = "llava-phi3:3.8b"
    web_search_threshold: float = 0.65
    tts_provider: str = "kokoro"
    tts_voice: str = "af_heart"

    upload_dir: str = "/data/uploads"
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 3
    similarity_threshold: float = 0.45

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
