"""Rerank + explication par LLM sur un nombre restreint de candidats.

But : donner un score final calibré (0-100) et une explication ancrée dans le
profil (compétence, poste, durée, secteur réellement présents), plutôt que la
seule similarité vectorielle qui n'explique rien. On ne rerank qu'un top-N
restreint (10-15) pour contrôler le coût.
"""
import json

from pydantic import BaseModel, Field

from cvsearch.config import get_settings
from cvsearch.llm.clients import chat_client
from cvsearch.llm.prompts import RERANK_SYSTEM, rerank_user_prompt
from cvsearch.schema import CVProfile, RankedResult


class _RerankItem(BaseModel):
    cv_id: str
    score: float
    explanation: str


class _RerankResponse(BaseModel):
    results: list[_RerankItem] = Field(default_factory=list)


def _candidate_summary(profile: CVProfile) -> dict:
    return {
        "cv_id": profile.cv_id,
        "full_name": profile.full_name,
        "headline": profile.headline,
        "seniority": profile.seniority,
        "years_professional": profile.years_professional,
        "years_by_industry": profile.years_by_industry,
        "skills": profile.skills,
        "experiences": [
            {
                "title": e.title,
                "company": e.company,
                "industry": e.industry,
                "technologies": e.technologies,
                "description": e.description[:400],
            }
            for e in profile.experiences
        ],
    }


def rerank(query: str, profiles: list[CVProfile]) -> list[RankedResult]:
    if not profiles:
        return []

    settings = get_settings()
    client = chat_client()
    candidates_json = json.dumps([_candidate_summary(p) for p in profiles], ensure_ascii=False)

    resp = client.chat.completions.parse(
        model=settings.chat_deployment,
        messages=[
            {"role": "system", "content": RERANK_SYSTEM},
            {"role": "user", "content": rerank_user_prompt(query, candidates_json)},
        ],
        max_completion_tokens=settings.max_completion_tokens,
        reasoning_effort=settings.reasoning_effort,
        response_format=_RerankResponse,
    )
    parsed = resp.choices[0].message.parsed

    by_id = {p.cv_id: p for p in profiles}
    if parsed is None or not parsed.results:
        # Repli : ordre d'entrée (post-fusion RRF), sans explication LLM.
        return [
            RankedResult(cv_id=p.cv_id, full_name=p.full_name, source_file=p.source_file,
                         score=0.0, explanation="Rerank indisponible ; ordre basé sur la fusion RRF.")
            for p in profiles
        ]

    results = []
    for item in parsed.results:
        profile = by_id.get(item.cv_id)
        if profile is None:
            continue
        results.append(
            RankedResult(
                cv_id=profile.cv_id,
                full_name=profile.full_name,
                source_file=profile.source_file,
                score=item.score,
                explanation=item.explanation,
            )
        )
    results.sort(key=lambda r: r.score, reverse=True)
    return results
