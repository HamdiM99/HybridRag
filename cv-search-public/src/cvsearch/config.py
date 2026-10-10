"""Configuration centralisée, chargée depuis les variables d'environnement / .env."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    apim_base_url: str
    apim_subscription_key: str
    chat_deployment: str = "gpt-5"
    embed_deployment: str = "text-embedding-3-large"
    api_version: str = "2025-01-01-preview"
    embed_dimensions: int = 1024

    # gpt-5 est un modèle de raisonnement : max_completion_tokens inclut les
    # tokens de raisonnement. La policy APIM impose <= 4000. Un reasoning_effort
    # trop élevé peut donc renvoyer une sortie vide/tronquée (finish_reason="length").
    max_completion_tokens: int = 4000
    reasoning_effort: str = "minimal"

    cache_dir: Path = Path("cache")
    index_dir: Path = Path("index")

    # Seuils métier, centralisés pour être facilement ajustables / testables.
    min_text_chars_for_text_mode: int = 400  # sous ce seuil -> bascule en mode vision
    internship_counts_as_experience: bool = False


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.cache_dir.mkdir(parents=True, exist_ok=True)
    s.index_dir.mkdir(parents=True, exist_ok=True)
    return s
