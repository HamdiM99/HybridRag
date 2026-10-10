#!/usr/bin/env python3
"""Vérifie que la gateway APIM répond correctement AVANT de lancer l'ingestion.

Teste spécifiquement les deux points fragiles avec gpt-5 derrière ce proxy :
1. Les sorties structurées (`response_format=<modèle Pydantic>`).
2. `reasoning_effort` + le plafond `max_completion_tokens` imposé par APIM (4000),
   qui inclut les tokens de raisonnement.

Lancer : `make smoke` ou `python scripts/smoke_test.py`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pydantic import BaseModel

from cvsearch.config import get_settings
from cvsearch.llm.clients import chat_client, embed_texts


class _Demo(BaseModel):
    answer: str
    confidence: float


def main() -> None:
    settings = get_settings()
    print(f"Base URL      : {settings.apim_base_url}")
    print(f"Chat deploy   : {settings.chat_deployment}")
    print(f"Embed deploy  : {settings.embed_deployment}")
    print(f"reasoning_effort={settings.reasoning_effort}  max_completion_tokens={settings.max_completion_tokens}")
    print()

    print("[1/2] Chat + sortie structurée...")
    client = chat_client()
    resp = client.chat.completions.parse(
        model=settings.chat_deployment,
        messages=[
            {"role": "system", "content": "Réponds uniquement avec le JSON demandé."},
            {"role": "user", "content": "La capitale de la France est-elle Paris ?"},
        ],
        max_completion_tokens=settings.max_completion_tokens,
        reasoning_effort=settings.reasoning_effort,
        response_format=_Demo,
    )
    choice = resp.choices[0]
    print(f"  finish_reason = {choice.finish_reason}")
    print(f"  parsed        = {choice.message.parsed}")
    if choice.finish_reason == "length" or choice.message.parsed is None:
        print("  /!\\ Sortie tronquée ou non parsée : réduire reasoning_effort ou "
              "gérer le repli JSON manuel (voir extraction/extractor.py).")
    else:
        print("  OK")
    print()

    print("[2/2] Embeddings (dimensions réduites)...")
    vecs = embed_texts(["Texte de test pour vérifier la dimension."])
    print(f"  dimension obtenue = {len(vecs[0])} (attendu: {settings.embed_dimensions})")
    print("  OK" if len(vecs[0]) == settings.embed_dimensions else "  /!\\ dimension inattendue")


if __name__ == "__main__":
    main()
