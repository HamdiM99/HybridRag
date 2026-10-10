"""Tests unitaires du calcul d'années d'expérience (logique 100% déterministe,
sans appel LLM ni réseau — c'est le cœur testable du pipeline)."""
from datetime import date

from cvsearch.extraction.experience import apply_declared_fallback, compute_experience
from cvsearch.schema import CVExtraction, Experience

TODAY = date(2026, 9, 29)


def _extraction(*experiences: Experience) -> CVExtraction:
    return CVExtraction(full_name="Test", experiences=list(experiences))


def test_simple_job_duration():
    exp = Experience(title="Dev", start="2020-01", end="2022-01", kind="job")
    years_pro, years_total, _ = compute_experience(_extraction(exp), today=TODAY)
    assert years_pro == 2.0
    assert years_total == 2.0


def test_present_uses_today():
    exp = Experience(title="Dev", start="2024-01", end="present", kind="job")
    years_pro, _, _ = compute_experience(_extraction(exp), today=TODAY)
    # 2024-01 -> 2026-09-29 ~= 2.74 ans
    assert 2.6 < years_pro < 2.9


def test_overlapping_jobs_not_double_counted():
    exp1 = Experience(title="Dev A", start="2020-01", end="2021-06", kind="job")
    exp2 = Experience(title="Dev B (temps partiel)", start="2021-01", end="2022-01", kind="job")
    years_pro, _, _ = compute_experience(_extraction(exp1, exp2), today=TODAY)
    # Union des deux périodes = 2020-01 -> 2022-01 = 2 ans, pas 2.5
    assert years_pro == 2.0


def test_internship_excluded_from_professional_by_default():
    internship = Experience(title="Stage", start="2019-06", end="2019-12", kind="internship")
    job = Experience(title="Dev", start="2020-01", end="2021-01", kind="job")
    years_pro, years_total, _ = compute_experience(_extraction(internship, job), today=TODAY)
    assert years_pro == 1.0  # seulement le job
    assert years_total > years_pro  # le stage compte dans le total


def test_industry_aggregation():
    exp1 = Experience(title="Consultant", start="2018-01", end="2020-01",
                       kind="job", industry="conseil")
    exp2 = Experience(title="Consultant senior", start="2020-01", end="2023-01",
                       kind="job", industry="conseil")
    _, _, by_industry = compute_experience(_extraction(exp1, exp2), today=TODAY)
    assert by_industry["conseil"] == 5.0


def test_unparsable_dates_are_ignored_not_guessed():
    exp = Experience(title="Dev", start="il y a longtemps", end="present", kind="job")
    years_pro, years_total, _ = compute_experience(_extraction(exp), today=TODAY)
    assert years_pro == 0.0
    assert years_total == 0.0


# --- Formats de date réels observés en sortie LLM (au-delà de "YYYY-MM" strict) ---
# Le prompt demande "YYYY-MM"/"YYYY", mais un test en conditions réelles a montré
# que le modèle reproduit parfois le format d'origine du CV. Ces tests couvrent
# les variantes qui avaient auparavant pour effet de faire échouer le parsing
# silencieusement (years_pro=0.0 malgré une expérience réelle sur le CV).

def test_iso_date_with_day_component():
    exp = Experience(title="Dev", start="2022-09-01", end="2023-12-31", kind="job")
    years_pro, _, _ = compute_experience(_extraction(exp), today=TODAY)
    assert 1.2 < years_pro < 1.3


def test_slash_month_year_format():
    exp = Experience(title="Dev", start="09/2022", end="12/2023", kind="job")
    years_pro, _, _ = compute_experience(_extraction(exp), today=TODAY)
    assert 1.2 < years_pro < 1.3


def test_french_month_name_format():
    exp = Experience(title="Dev", start="Septembre 2022", end="Décembre 2023", kind="job")
    years_pro, _, _ = compute_experience(_extraction(exp), today=TODAY)
    assert 1.2 < years_pro < 1.3


def test_english_abbreviated_month_name_format():
    exp = Experience(title="Dev", start="Sep 2022", end="present", kind="job")
    years_pro, _, _ = compute_experience(_extraction(exp), today=TODAY)
    assert years_pro > 3.9


def test_prefixed_text_around_date_still_parses():
    # Le LLM peut renvoyer "Depuis 2021" plutôt que juste "2021".
    exp = Experience(title="Dev", start="Depuis 2021", end="present", kind="job")
    years_pro, _, _ = compute_experience(_extraction(exp), today=TODAY)
    assert years_pro > 5.5


# --- Repli sur le total déclaré (cas réel : CV une-page en PPTX qui affiche
# "3 years of experience" en en-tête sans dater chaque poste individuellement)

def test_declared_fallback_used_when_no_dates_computed():
    years, source = apply_declared_fallback(0.0, 3.0)
    assert years == 3.0
    assert source == "declared"


def test_declared_fallback_not_used_when_dates_did_compute():
    # Un calcul par dates réussi (même partiel) ne doit JAMAIS être écrasé
    # par le total déclaré, même s'ils diffèrent.
    years, source = apply_declared_fallback(5.9, 10.0)
    assert years == 5.9
    assert source == "computed"


def test_no_fallback_when_neither_source_available():
    years, source = apply_declared_fallback(0.0, None)
    assert years == 0.0
    assert source == "none"


def test_declared_fallback_ignores_zero_or_negative_declared_value():
    years, source = apply_declared_fallback(0.0, 0.0)
    assert years == 0.0
    assert source == "none"
