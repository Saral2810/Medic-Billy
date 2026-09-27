"""All settings come from environment variables (or a .env file).

The same code runs as two programs:
  * the backend API (website side)  -> uses the database, storage, Redis and worker-token settings
  * the worker (GPU machine side)   -> uses BACKEND_URL, WORKER_TOKEN and the model settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ---------- backend (website side) ----------
    database_url: str = "postgresql+psycopg://billtrail:billtrail@localhost:5432/billtrail"
    storage_dir: str = "./storage/originals"          # originals are written here, never edited
    max_upload_mb: int = 15
    redis_url: str = "redis://localhost:6379/0"       # job queue
    stale_job_seconds: int = 900                      # a job "processing" longer than this is put back in the queue
    review_confidence: float = 0.7                    # below this, a person must review
    cors_origins: str = "http://localhost:3000"

    # shared secret between backend and worker (the worker sends it in X-Worker-Token)
    worker_token: str = "change-me"

    # ---------- worker (GPU machine side) ----------
    backend_url: str = "http://localhost:8000"
    worker_name: str = "gpu-worker-1"
    poll_seconds: float = 3.0

    # Which model reads the bill:
    #   qwen_local = our fine-tuned Qwen3-VL served by vLLM or Ollama (OpenAI-compatible API)  <- main system
    #   claude     = Anthropic Claude (used only as teacher for labels and as a baseline)
    llm_provider: str = "qwen_local"
    # What the model sees:
    #   vision   = the cleaned bill image (main system)
    #   ocr_text = Tesseract/PaddleOCR text only (baseline for the paper)
    extract_mode: str = "vision"
    ocr_engine: str = "tesseract"                     # "tesseract" or "paddle" (only for extract_mode=ocr_text)

    qwen_base_url: str = "http://localhost:8001/v1"   # vLLM default in docker-compose; Ollama is http://localhost:11434/v1
    qwen_model: str = "billtrail-qwen3vl"             # the served model name
    qwen_api_key: str = "not-needed"                  # vLLM/Ollama ignore it unless you set one

    anthropic_api_key: str = ""
    claude_model: str = "claude-sonnet-5"

    llm_max_tokens: int = 4000
    max_pages: int = 3                                # PDF pages sent to the model
    max_image_side: int = 1600                        # pixels; bigger images are shrunk (fewer tokens, same readability)


settings = Settings()
