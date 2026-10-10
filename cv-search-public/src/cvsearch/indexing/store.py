"""Store vectoriel + BM25, avec index dérivé des CV structurés.

Choix pour cette démo (petit corpus, budget contraint) : un store local fichier
(JSON + tableau numpy pickled), reconstruit facilement depuis `cache/` puisque
le JSON structuré est la source de vérité, pas l'index. Interface volontairement
étroite (`VectorStore`) pour permettre de brancher Qdrant ou Azure AI Search en
production sans changer le reste du pipeline — voir README, section
"Passage en production".
"""
from __future__ import annotations

import pickle
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from rank_bm25 import BM25Okapi

from cvsearch.config import get_settings
from cvsearch.schema import CVProfile

# Tokenisation BM25 : \w+ (mots Unicode, gère les accents nativement) plutôt
# qu'un split naïf sur les espaces. Défaut observé : du texte
# comme "FR |EN |DE | FA" (langues d'un CV, ponctuation collée aux mots) se
# découpait en ["fr", "|en", "|de", "|", "fa"] avec un simple .split() — "en"
# et "de" devenaient des tokens avec le "|" collé, ne matchant plus jamais une
# requête contenant "en" ou "de" seuls. _TOKEN_RE isole les mots et ignore la
# ponctuation (|, /, parenthèses, virgules...), que le mot soit collé ou non.
_TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class ChunkRecord:
    cv_id: str
    chunk_id: str
    chunk_kind: str  # "summary", "experience", "skills"
    text: str
    embedding: np.ndarray


@dataclass
class IndexStore:
    chunks: list[ChunkRecord] = field(default_factory=list)
    profiles: dict[str, CVProfile] = field(default_factory=dict)
    _bm25: BM25Okapi | None = field(default=None, repr=False)
    _tokenized: list[list[str]] = field(default_factory=list, repr=False)

    def add_profile(self, profile: CVProfile, chunk_texts: list[tuple[str, str, str]],
                     embeddings: list[list[float]]) -> None:
        """chunk_texts: liste de (chunk_id, chunk_kind, text), même longueur que embeddings."""
        self.profiles[profile.cv_id] = profile
        for (chunk_id, kind, text), emb in zip(chunk_texts, embeddings):
            self.chunks.append(
                ChunkRecord(
                    cv_id=profile.cv_id,
                    chunk_id=chunk_id,
                    chunk_kind=kind,
                    text=text,
                    embedding=np.array(emb, dtype=np.float32),
                )
            )
        self._rebuild_bm25()

    def _rebuild_bm25(self) -> None:
        self._tokenized = [_tokenize(c.text) for c in self.chunks]
        self._bm25 = BM25Okapi(self._tokenized) if self._tokenized else None

    def dense_search(self, query_embedding: list[float], top_k: int) -> list[tuple[ChunkRecord, float]]:
        if not self.chunks:
            return []
        q = np.array(query_embedding, dtype=np.float32)
        q_norm = q / (np.linalg.norm(q) + 1e-8)
        scored = []
        for chunk in self.chunks:
            c_norm = chunk.embedding / (np.linalg.norm(chunk.embedding) + 1e-8)
            score = float(np.dot(q_norm, c_norm))
            scored.append((chunk, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def bm25_search(self, query: str, top_k: int) -> list[tuple[ChunkRecord, float]]:
        if self._bm25 is None:
            return []
        scores = self._bm25.get_scores(_tokenize(query))
        ranked = sorted(zip(self.chunks, scores), key=lambda x: x[1], reverse=True)
        return [(c, s) for c, s in ranked[:top_k] if s > 0]

    def save(self, path: Path | None = None) -> None:
        path = path or (get_settings().index_dir / "store.pkl")
        with open(path, "wb") as f:
            pickle.dump({"chunks": self.chunks, "profiles": self.profiles}, f)

    @classmethod
    def load(cls, path: Path | None = None) -> "IndexStore":
        path = path or (get_settings().index_dir / "store.pkl")
        store = cls()
        if path.exists():
            with open(path, "rb") as f:
                data = pickle.load(f)
            store.chunks = data["chunks"]
            store.profiles = data["profiles"]
            store._rebuild_bm25()
        return store
