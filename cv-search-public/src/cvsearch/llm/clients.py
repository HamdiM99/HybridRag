"""Clients Azure OpenAI derrière la gateway APIM.

APIM attend la clé dans l'en-tête ``Ocp-Apim-Subscription-Key`` ; ``api_key``
est un placeholder requis par le SDK mais ignoré côté gateway. Le endpoint
embeddings est distinct (``{base}/embeddings``), donc deux clients séparés.
"""
from functools import lru_cache

from openai import AzureOpenAI

from cvsearch.config import Settings, get_settings


def _make_client(endpoint: str, s: Settings) -> AzureOpenAI:
    return AzureOpenAI(
        api_version=s.api_version,
        azure_endpoint=endpoint,
        api_key="placeholder",
        default_headers={"Ocp-Apim-Subscription-Key": s.apim_subscription_key},
        max_retries=5,  # backoff intégré du SDK pour les 429/503
    )


@lru_cache
def chat_client() -> AzureOpenAI:
    s = get_settings()
    return _make_client(s.apim_base_url, s)


@lru_cache
def embed_client() -> AzureOpenAI:
    s = get_settings()
    return _make_client(f"{s.apim_base_url}/embeddings", s)


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Vectorise une liste de textes. Découpe en lots pour rester raisonnable."""
    s = get_settings()
    out: list[list[float]] = []
    batch_size = 16
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        res = embed_client().embeddings.create(
            model=s.embed_deployment, input=batch, dimensions=s.embed_dimensions
        )
        out.extend(d.embedding for d in res.data)
    return out
