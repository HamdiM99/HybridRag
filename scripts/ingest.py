#!/usr/bin/env python3
"""Ingestion en lot d'un dossier de CV. Usage : python scripts/ingest.py data/cvs"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cvsearch.pipeline import ingest_directory


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest.py <dossier>")
        sys.exit(1)

    directory = Path(sys.argv[1])
    if not directory.is_dir():
        print(f"Dossier introuvable : {directory}")
        sys.exit(1)

    profiles = ingest_directory(directory)
    print(f"{len(profiles)} CV indexés :")
    for p in profiles:
        print(f"  - {p.full_name:30s} mode={p.parsing_mode:6s} "
              f"years_pro={p.years_professional:.1f} ({p.years_source:9s}) "
              f"source={Path(p.source_file).name}")

    # Diagnostic : un CV avec des expériences détectées mais years_source="none"
    # signale un cas où ni les dates par poste ni un total déclaré n'ont pu
    # être exploités (voir extraction/experience.py:apply_declared_fallback).
    # On affiche les dates brutes renvoyées par le LLM pour chaque expérience,
    # ce qui permet de diagnostiquer sans ouvrir soi-même les fichiers de cache.
    suspects = [p for p in profiles if p.years_source == "none" and p.experiences]
    if suspects:
        print("\n/!\\ CV avec expérience(s) détectée(s) mais aucune durée exploitable "
              "(ni dates par poste, ni total déclaré) :")
        for p in suspects:
            print(f"\n  {p.full_name} ({Path(p.source_file).name}) "
                  f"declared_years_experience={p.declared_years_experience!r} :")
            for exp in p.experiences:
                print(f"    - kind={exp.kind:14s} start={exp.start!r:15s} "
                      f"end={exp.end!r:15s} title={exp.title}")


if __name__ == "__main__":
    main()
