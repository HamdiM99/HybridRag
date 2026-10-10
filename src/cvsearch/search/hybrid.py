"""Fusion dense + BM25 (RRF) et application des filtres durs extraits de la requête.

RRF (Reciprocal Rank Fusion) plutôt qu'une moyenne pondérée de scores bruts :
les échelles de score dense (cosinus, ~0-1) et BM25 (non borné) ne sont pas
comparables directement, RRF ne dépend que du rang de chaque candidat dans
chaque liste, ce qui est plus robuste sans calibration fine.

Chaque retriever classe des chunks. Pour chaque retriever, on ne garde que le
meilleur chunk de chaque candidat (max), ce qui donne un classement de
candidats ; la fusion RRF standard additionne ensuite les contributions des
retrievers (voir `fuse_rankings`).
"""
from cvsearch.indexing.store import IndexStore
from cvsearch.llm.clients import embed_texts
from cvsearch.schema import CVProfile, SearchFilters

RRF_K = 60


def _passes_hard_filters(profile: CVProfile, filters: SearchFilters) -> bool:
    """Applique les filtres durs extraits de la requête.

    Important : quand un secteur est demandé en même temps qu'un seuil
    d'années (ex. "au moins 10 ans dans le conseil"), le seuil s'applique
    aux années DANS ce secteur (`years_by_industry[secteur]`), pas au total
    professionnel toutes industries confondues. Sans cette distinction, un
    candidat avec 14 ans d'expérience dont seulement 1 an dans le secteur
    demandé passerait à tort le filtre — vérifié en conditions réelles.
    """
    if filters.required_industry:
        years_in_industry = profile.years_by_industry.get(filters.required_industry, 0.0)
        if years_in_industry <= 0:
            return False
        if filters.min_years_experience is not None:
            if years_in_industry < filters.min_years_experience:
                return False
    elif filters.min_years_experience is not None:
        if profile.years_professional < filters.min_years_experience:
            return False
    return True


def fuse_rankings(rankings: list[list[str]], k: int = RRF_K) -> dict[str, float]:
    """RRF standard sur des classements de candidats : score(d) = somme 1/(k + rang).

    Chaque élément de `rankings` est la liste, du meilleur au moins bon, des
    cv_id remontés par UN retriever. Un même cv_id peut y apparaître plusieurs
    fois (un chunk par occurrence) : seule sa première occurrence, donc son
    meilleur chunk, compte (max, pas somme). Le rang est ensuite calculé parmi
    les candidats distincts, à partir de 1. Un candidat remonté par plusieurs
    retrievers voit ses contributions s'additionner.
    """
    fused: dict[str, float] = {}
    for ranking in rankings:
        distinct = list(dict.fromkeys(ranking))  # meilleur chunk de chaque candidat
        for rank, cv_id in enumerate(distinct, start=1):
            fused[cv_id] = fused.get(cv_id, 0.0) + 1.0 / (k + rank)
    return fused


def candidate_scores(store: IndexStore, filters: SearchFilters, top_k_chunks: int = 30) -> dict[str, float]:
    """Retourne {cv_id: score RRF}, après application des filtres durs."""
    query_embedding = embed_texts([filters.semantic_query])[0]

    dense = store.dense_search(query_embedding, top_k_chunks)
    bm25 = store.bm25_search(filters.semantic_query, top_k_chunks)

    fused = fuse_rankings([
        [chunk.cv_id for chunk, _score in dense],
        [chunk.cv_id for chunk, _score in bm25],
    ])

    # Filtres durs : on retire les candidats qui ne les satisfont pas plutôt
    # que de les pénaliser doucement — "min 10 ans" est une contrainte, pas une
    # préférence.
    return {
        cv_id: score
        for cv_id, score in fused.items()
        if _passes_hard_filters(store.profiles[cv_id], filters)
    }
