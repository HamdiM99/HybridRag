"""Orchestration haut niveau : ingestion et recherche.

C'est le point d'entrée commun à l'API, au CLI et au script d'évaluation, pour
éviter que la logique diverge entre les trois surfaces.
"""
from pathlib import Path

from cvsearch.extraction.extractor import extract_cv
from cvsearch.indexing.build import index_profile
from cvsearch.indexing.store import IndexStore
from cvsearch.schema import CVProfile, RankedResult
from cvsearch.search.hybrid import candidate_scores
from cvsearch.search.query import understand_query
from cvsearch.search.rerank import rerank

SUPPORTED_SUFFIXES = {".pdf", ".docx", ".pptx"}

# Store en mémoire, persisté sur disque entre les runs (voir indexing/store.py).
_store: IndexStore | None = None


def get_store() -> IndexStore:
    global _store
    if _store is None:
        _store = IndexStore.load()
    return _store


def ingest_file(path: Path) -> CVProfile:
    profile = extract_cv(path)
    index_profile(get_store(), profile)
    get_store().save()
    return profile


def ingest_directory(directory: Path) -> list[CVProfile]:
    profiles = []
    for path in sorted(directory.rglob("*")):
        if path.suffix.lower() in SUPPORTED_SUFFIXES:
            profiles.append(ingest_file(path))
    return profiles


def search(query: str, top_k: int = 5, rerank_pool: int = 12) -> list[RankedResult]:
    store = get_store()
    filters = understand_query(query)
    scores = candidate_scores(store, filters)

    if not scores:
        return []

    ranked_cv_ids = sorted(scores, key=scores.get, reverse=True)[:rerank_pool]
    profiles = [store.profiles[cv_id] for cv_id in ranked_cv_ids]

    results = rerank(query, profiles)
    return results[:top_k]
