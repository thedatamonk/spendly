from app.config import get_settings
from app.db.repository import ObligationRepository
from app.llm.parser import IntentParser

settings = get_settings()

repo = ObligationRepository(settings.db_path)
parser = IntentParser(api_key=settings.openrouter_api_key, model=settings.llm_model)
