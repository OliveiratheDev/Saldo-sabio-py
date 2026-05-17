import os
from pathlib import Path

from dotenv import load_dotenv

# Carrega segredos de src/.env (cria a partir de .env.example; não commits .env).
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///saldosabio.db")
API_KEY = os.getenv("API_KEY", "")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
