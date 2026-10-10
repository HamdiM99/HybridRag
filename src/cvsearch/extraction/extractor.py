"""Extraction LLM d'un CV vers `CVProfile`, avec cache par hash de fichier.

Le cache évite de repayer un CV déjà traité (important avec un budget de test
limité). Le LLM extrait uniquement (voir prompts.EXTRACTION_SYSTEM) ; le calcul
des années d'expérience est fait en code (extraction/experience.py).
"""
import hashlib
import json
from pathlib import Path

from cvsearch.config import get_settings
from cvsearch.llm.clients import chat_client
from cvsearch.llm.prompts import (
    EXTRACTION_SYSTEM,
    VISION_EXTRACTION_SYSTEM,
    extraction_user_prompt,
)
from cvsearch.parsing.extract_text import extract
from cvsearch.parsing.vision import build_vision_content
from cvsearch.extraction.experience import apply_declared_fallback, compute_experience
from cvsearch.schema import CVExtraction, CVProfile


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()[:16]


def _cache_path(cv_id: str) -> Path:
    return get_settings().cache_dir / f"{cv_id}.json"


def _call_llm_structured(system: str, content) -> CVExtraction:
    settings = get_settings()
    client = chat_client()
    resp = client.chat.completions.parse(
        model=settings.chat_deployment,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": content},
        ],
        max_completion_tokens=settings.max_completion_tokens,
        reasoning_effort=settings.reasoning_effort,
        response_format=CVExtraction,
    )
    choice = resp.choices[0]
    if choice.finish_reason == "length" or choice.message.parsed is None:
        # gpt-5 : max_completion_tokens inclut le raisonnement -> troncature possible.
        # Repli : parsing manuel du JSON brut si présent, sinon échec explicite.
        raw = choice.message.content
        if not raw:
            raise RuntimeError(
                "Réponse tronquée par le modèle (finish_reason=length) sans "
                "contenu exploitable. Augmenter max_completion_tokens ou "
                "réduire reasoning_effort."
            )
        return CVExtraction.model_validate(json.loads(raw))
    return choice.message.parsed


def extract_cv(path: Path, *, use_cache: bool = True) -> CVProfile:
    cv_id = _file_hash(path)
    cache_file = _cache_path(cv_id)

    if use_cache and cache_file.exists():
        return CVProfile.model_validate_json(cache_file.read_text(encoding="utf-8"))

    extraction_result = extract(path)

    if extraction_result.mode == "needs_vision":
        content = build_vision_content(extraction_result.text, extraction_result.image_paths)
        cv_extraction = _call_llm_structured(VISION_EXTRACTION_SYSTEM, content)
        parsing_mode = "vision"
    else:
        prompt = extraction_user_prompt(extraction_result.text)
        cv_extraction = _call_llm_structured(EXTRACTION_SYSTEM, prompt)
        parsing_mode = "text"

    years_professional, years_total, years_by_industry = compute_experience(cv_extraction)
    years_professional, years_source = apply_declared_fallback(
        years_professional, cv_extraction.declared_years_experience
    )

    profile = CVProfile(
        **cv_extraction.model_dump(),
        cv_id=cv_id,
        source_file=str(path),
        parsing_mode=parsing_mode,
        years_professional=years_professional,
        years_total=years_total,
        years_by_industry=years_by_industry,
        years_source=years_source,
    )

    if use_cache:
        cache_file.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return profile
