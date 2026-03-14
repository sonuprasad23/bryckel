import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "stepfun/step-3.5-flash:free")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
TOP_K_CHUNKS = 5
