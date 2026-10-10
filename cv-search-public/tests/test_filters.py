"""Tests des filtres durs (fonction pure, aucun appel réseau).

Bug réel observé : un candidat avec beaucoup d'années professionnelles au
total mais peu dans le secteur demandé passait à tort le filtre
"min_years_experience" + "required_industry" combinés, car le seuil était
comparé au total toutes industries plutôt qu'aux années dans ce secteur.
"""
from cvsearch.schema import CVProfile, SearchFilters
from cvsearch.search.hybrid import _passes_hard_filters


def _profile(years_professional: float, years_by_industry: dict[str, float]) -> CVProfile:
    return CVProfile(
        full_name="Test",
        cv_id="abc123",
        source_file="test.pdf",
        parsing_mode="text",
        years_professional=years_professional,
        years_total=years_professional,
        years_by_industry=years_by_industry,
    )


def test_high_total_but_low_industry_years_is_rejected():
    # 14.5 ans au total, mais seulement 0.92 an dans le secteur demandé :
    # ne doit PAS passer un filtre "10 ans dans le conseil".
    profile = _profile(14.5, {"conseil": 0.92, "e-commerce": 13.5})
    filters = SearchFilters(semantic_query="x", min_years_experience=10, required_industry="conseil")
    assert _passes_hard_filters(profile, filters) is False


def test_sufficient_industry_years_passes():
    profile = _profile(12.0, {"conseil": 11.0})
    filters = SearchFilters(semantic_query="x", min_years_experience=10, required_industry="conseil")
    assert _passes_hard_filters(profile, filters) is True


def test_industry_absent_is_rejected():
    profile = _profile(20.0, {"banque": 20.0})
    filters = SearchFilters(semantic_query="x", min_years_experience=None, required_industry="conseil")
    assert _passes_hard_filters(profile, filters) is False


def test_min_years_without_industry_uses_total_professional():
    profile = _profile(6.0, {})
    filters = SearchFilters(semantic_query="x", min_years_experience=5, required_industry=None)
    assert _passes_hard_filters(profile, filters) is True

    filters_too_high = SearchFilters(semantic_query="x", min_years_experience=8, required_industry=None)
    assert _passes_hard_filters(profile, filters_too_high) is False


def test_no_filters_always_passes():
    profile = _profile(0.0, {})
    filters = SearchFilters(semantic_query="x")
    assert _passes_hard_filters(profile, filters) is True


# --- Tokenisation BM25 (régression réelle) ---
# "FR |EN |DE | FA" (langues d'un CV, ponctuation collée aux mots) se
# découpait en ["fr", "|en", "|de", "|", "fa"] avec un split() naïf : "en" et
# "de" ne matchaient plus jamais une requête les contenant seuls.

from cvsearch.indexing.store import _tokenize


def test_tokenize_strips_punctuation_glued_to_words():
    assert _tokenize("FR |EN |DE | FA") == ["fr", "en", "de", "fa"]


def test_tokenize_preserves_accents():
    assert _tokenize("Expérience en développement") == ["expérience", "en", "développement"]


def test_tokenize_splits_on_slash_and_parentheses():
    assert _tokenize("Data Scientist / Data Engineer (Azure, AWS)") == [
        "data", "scientist", "data", "engineer", "azure", "aws",
    ]
