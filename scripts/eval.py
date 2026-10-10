#!/usr/bin/env python3
"""Exécute les 5 requêtes RH d'exemple (data/eval_queries.json) et affiche les résultats.

Sert de mini-évaluation qualitative : pas de vérité terrain automatique sur ce
corpus (10 CV), donc affichage clair pour relecture humaine plutôt qu'un score
agrégé qui donnerait une fausse précision.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cvsearch.pipeline import search


def main() -> None:
    queries_path = Path(__file__).resolve().parents[1] / "data" / "eval_queries.json"
    # encoding="utf-8" explicite : sans lui, Path.read_text() utilise l'encodage
    # local (cp1252 sur Windows) et corrompt les accents ("expérience" -> "expÃ©rience").
    queries = json.loads(queries_path.read_text(encoding="utf-8"))

    for item in queries:
        print("=" * 100)
        print(f"REQUÊTE : {item['query']}")
        print(f"Attendu : {item['notes']}")
        print("-" * 100)
        results = search(item["query"], top_k=5)
        if not results:
            print("  Aucun résultat (aucun candidat ne passe les filtres, ou score trop faible).")
        for r in results:
            print(f"  [{r.score:5.1f}] {r.full_name:25s} — {r.explanation}")
        print()


if __name__ == "__main__":
    main()
