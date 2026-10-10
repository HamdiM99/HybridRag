"""Construction des chunks à indexer à partir d'un `CVProfile`.

Chunking par section plutôt que par taille fixe : un chunk pour le résumé/profil,
un chunk par expérience (titre + description + secteur + technologies), un chunk
pour les compétences. On agrège ensuite par candidat au moment de la recherche
(cf. search/hybrid.py) : le score d'un candidat est le meilleur score parmi ses
chunks, pas une moyenne qui dilue une expérience très pertinente.
"""
from cvsearch.llm.clients import embed_texts
from cvsearch.indexing.store import IndexStore
from cvsearch.schema import CVProfile


def _profile_chunks(profile: CVProfile) -> list[tuple[str, str, str]]:
    chunks: list[tuple[str, str, str]] = []

    summary_text = " | ".join(
        filter(None, [profile.headline, profile.summary, ", ".join(profile.skills)])
    )
    if summary_text.strip():
        chunks.append((f"{profile.cv_id}_summary", "summary", summary_text))

    for i, exp in enumerate(profile.experiences):
        parts = [exp.title]
        if exp.company:
            parts.append(exp.company)
        if exp.industry:
            parts.append(f"secteur: {exp.industry}")
        if exp.description:
            parts.append(exp.description)
        if exp.technologies:
            parts.append("technologies: " + ", ".join(exp.technologies))
        text = " | ".join(parts)
        chunks.append((f"{profile.cv_id}_exp{i}", "experience", text))

    if profile.skills:
        chunks.append(
            (f"{profile.cv_id}_skills", "skills", "Compétences : " + ", ".join(profile.skills))
        )

    return chunks


def index_profile(store: IndexStore, profile: CVProfile) -> None:
    chunk_defs = _profile_chunks(profile)
    if not chunk_defs:
        return
    texts = [text for _, _, text in chunk_defs]
    embeddings = embed_texts(texts)
    store.add_profile(profile, chunk_defs, embeddings)
