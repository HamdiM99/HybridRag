"""Calcul déterministe des années d'expérience à partir des expériences extraites.

Choix explicite (à documenter comme hypothèse métier dans le README) :
- `years_professional` : somme des périodes de type "job" et "freelance",
  chevauchements fusionnés (deux postes simultanés ne comptent pas double).
- `years_total` : idem mais inclut aussi stages et apprentissages.
- `years_by_industry` : somme par secteur déclaré (sur les périodes fusionnées
  par secteur, pas de double comptage si deux postes du même secteur se
  recoupent).
- Les stages/apprentissages sont exclus de `years_professional` par défaut
  (`Settings.internship_counts_as_experience` permet de changer ce choix).

Le LLM ne fait AUCUN calcul de durée : il reporte les dates telles qu'écrites.
Toute la logique temporelle vit ici, testée unitairement (voir tests/).

Note sur la robustesse du parsing : malgré une consigne explicite dans le
prompt d'extraction ("YYYY-MM" ou "YYYY" uniquement), un test en conditions
réelles a montré que le modèle reproduit parfois le format d'origine du CV
(dates ISO complètes, "MM/YYYY", noms de mois en toutes lettres, "Depuis
2021"...). Le parseur ci-dessous est donc volontairement tolérant : il
recherche un motif de date DANS la chaîne plutôt que d'exiger une
correspondance exacte sur toute la chaîne, et couvre les formats numériques
et textuels (FR/EN) les plus courants. Une date qu'il ne reconnaît toujours
pas est ignorée (période exclue du calcul), jamais devinée.
"""
import re
import unicodedata
from datetime import date

from cvsearch.config import get_settings
from cvsearch.schema import CVExtraction, Experience

_PRESENT_WORDS = {
    "present", "actuel", "actuelle", "aujourd'hui", "aujourdhui",
    "current", "now", "en cours", "à ce jour", "a ce jour", "ongoing",
}

# Formats numériques recherchés (pas ancrés en ^$ : on cherche le motif dans
# la chaîne, car le LLM peut entourer la date de texte, ex. "Depuis 09/2022").
_ISO_DATE = re.compile(r"(\d{4})-(\d{1,2})(?:-\d{1,2})?")  # YYYY-MM ou YYYY-MM-DD
_SLASH_MY = re.compile(r"(\d{1,2})/(\d{4})")  # MM/YYYY
_SLASH_YM = re.compile(r"(\d{4})/(\d{1,2})")  # YYYY/MM
_YEAR_ONLY = re.compile(r"\b(\d{4})\b")

_MONTHS = {
    "jan": 1, "janv": 1, "janvier": 1, "january": 1,
    "fev": 2, "fevr": 2, "fevrier": 2, "feb": 2, "february": 2,
    "mar": 3, "mars": 3, "march": 3,
    "avr": 4, "avril": 4, "apr": 4, "april": 4,
    "mai": 5, "may": 5,
    "juin": 6, "jun": 6, "june": 6,
    "juil": 7, "juillet": 7, "jul": 7, "july": 7,
    "aou": 8, "août": 8, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "septembre": 9, "september": 9,
    "oct": 10, "octobre": 10, "october": 10,
    "nov": 11, "novembre": 11, "november": 11,
    "dec": 12, "dece": 12, "decembre": 12, "décembre": 12, "december": 12,
}
_MONTH_NAME_YEAR = re.compile(
    r"([a-zA-Zéûîôâêàèùçëï]{3,})\.?\s+(\d{4})"
)


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def _month_from_word(word: str) -> int | None:
    key = _strip_accents(word.lower()).rstrip(".")
    # essaie le mot complet, puis des préfixes de plus en plus courts
    # (couvre "septembre", "sept", "sep" pour la même valeur)
    for length in (len(key), 7, 4, 3):
        candidate = key[:length]
        if candidate in _MONTHS:
            return _MONTHS[candidate]
    return None


def _parse_date(value: str | None, *, is_end: bool, today: date) -> date | None:
    """Convertit une date de CV en `date` Python, de façon tolérante.

    Gère : "YYYY", "YYYY-MM", "YYYY-MM-DD", "MM/YYYY", "YYYY/MM",
    "Septembre 2022", "Sep 2022", et les marqueurs de poste en cours
    ("present", "actuel", "en cours", ...) pour une date de fin.

    Pour une date de fin manquante ou marquée "en cours", renvoie `today`.
    Pour une date de début manquante ou illisible, renvoie None (période
    ignorée dans le calcul plutôt que devinée).
    """
    if value is None or not value.strip():
        return today if is_end else None

    v = value.strip().lower()
    if is_end and any(word in v for word in _PRESENT_WORDS):
        return today

    m = _ISO_DATE.search(v)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return date(year, month, 1)

    m = _SLASH_MY.search(v)
    if m:
        month, year = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return date(year, month, 1)

    m = _SLASH_YM.search(v)
    if m:
        year, month = int(m.group(1)), int(m.group(2))
        if 1 <= month <= 12:
            return date(year, month, 1)

    m = _MONTH_NAME_YEAR.search(v)
    if m:
        month = _month_from_word(m.group(1))
        if month is not None:
            return date(int(m.group(2)), month, 1)

    m = _YEAR_ONLY.search(v)
    if m:
        # Convention : année seule -> 1er janvier pour un début, 31 décembre pour une fin.
        year = int(m.group(1))
        return date(year, 12, 31) if is_end else date(year, 1, 1)

    return None  # date illisible : période ignorée plutôt que de deviner


def _period(exp: Experience, today: date) -> tuple[date, date] | None:
    start = _parse_date(exp.start, is_end=False, today=today)
    end = _parse_date(exp.end, is_end=True, today=today)
    if start is None or end is None or end < start:
        return None
    return start, end


def _merge_intervals(intervals: list[tuple[date, date]]) -> list[tuple[date, date]]:
    """Fusionne les intervalles qui se chevauchent ou se touchent."""
    if not intervals:
        return []
    intervals = sorted(intervals, key=lambda p: p[0])
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _years_from_intervals(intervals: list[tuple[date, date]]) -> float:
    merged = _merge_intervals(intervals)
    total_days = sum((end - start).days for start, end in merged)
    return round(total_days / 365.25, 2)


def apply_declared_fallback(
    years_professional: float, declared_years_experience: float | None
) -> tuple[float, str]:
    """Replis sur le total déclaré en texte libre si aucune date par poste
    n'a pu être calculée.

    Cas réel rencontré : des CV en une slide (souvent en PPTX) qui affichent
    "3 years of experience" en en-tête mais ne datent aucun poste
    individuellement. Sans ce repli, years_professional resterait à 0 pour un
    candidat manifestement expérimenté, ce qui l'exclurait à tort des filtres
    "au moins N ans". Le repli ne s'applique QUE si le calcul par dates a
    échoué (0) ET qu'un total est explicitement déclaré dans le CV — jamais
    pour remplacer un calcul par dates qui a réussi, même partiellement.

    Retourne (years, source) où source vaut "computed" ou "declared" ou "none"
    — exposé sur `CVProfile.years_source` pour la transparence.
    """
    if years_professional > 0:
        return years_professional, "computed"
    if declared_years_experience is not None and declared_years_experience > 0:
        return declared_years_experience, "declared"
    return 0.0, "none"


def compute_experience(
    extraction: CVExtraction, *, today: date | None = None
) -> tuple[float, float, dict[str, float]]:
    """Retourne (years_professional, years_total, years_by_industry).

    N'applique PAS le repli sur `declared_years_experience` : voir
    `apply_declared_fallback`, appelée séparément par l'appelant (garde le
    calcul par dates pur et testable indépendamment du repli déclaratif).
    """
    settings = get_settings()
    today = today or date.today()

    professional_kinds = {"job", "freelance"}
    if settings.internship_counts_as_experience:
        professional_kinds |= {"internship", "apprenticeship"}

    all_periods: list[tuple[date, date]] = []
    professional_periods: list[tuple[date, date]] = []
    by_industry: dict[str, list[tuple[date, date]]] = {}

    for exp in extraction.experiences:
        period = _period(exp, today)
        if period is None:
            continue
        all_periods.append(period)
        if exp.kind in professional_kinds:
            professional_periods.append(period)
        if exp.industry:
            by_industry.setdefault(exp.industry, []).append(period)

    years_total = _years_from_intervals(all_periods)
    years_professional = _years_from_intervals(professional_periods)
    years_by_industry = {
        industry: _years_from_intervals(periods) for industry, periods in by_industry.items()
    }
    return years_professional, years_total, years_by_industry
