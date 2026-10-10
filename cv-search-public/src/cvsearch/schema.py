"""Schémas de données pour les CV.

`CVExtraction` est rempli par le LLM (dates telles qu'écrites, pas de calcul).
`CVProfile` ajoute les champs calculés en code (années d'expérience) : le LLM
extrait, le code calcule — voir extraction/experience.py.
"""
from typing import Literal

from pydantic import BaseModel, Field

Seniority = Literal["student", "junior", "confirmed", "senior", "lead_manager", "unknown"]
ExperienceKind = Literal["job", "internship", "apprenticeship", "freelance", "other"]


class Experience(BaseModel):
    title: str
    company: str | None = None
    start: str | None = None  # "YYYY-MM" ou "YYYY" ; null si absent/illisible
    end: str | None = None  # "YYYY-MM", "YYYY" ou "present" ; null si absent
    kind: ExperienceKind = "job"
    industry: str | None = None  # ex: "conseil", "banque" (français, minuscule)
    description: str = ""
    technologies: list[str] = Field(default_factory=list)


class Education(BaseModel):
    degree: str
    school: str | None = None
    start_year: int | None = None
    end_year: int | None = None


class CVExtraction(BaseModel):
    full_name: str
    headline: str | None = None
    seniority: Seniority = "unknown"
    declared_years_experience: float | None = None  # tel qu'écrit, ex "5 ans"
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experiences: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class CVProfile(CVExtraction):
    cv_id: str  # sha256 du fichier source
    source_file: str
    parsing_mode: Literal["text", "vision"]
    years_professional: float = 0.0  # job + freelance, chevauchements fusionnés
    years_total: float = 0.0  # tous types confondus (stages inclus)
    years_by_industry: dict[str, float] = Field(default_factory=dict)
    # "computed" : calculé à partir des dates par poste (cas normal).
    # "declared" : repli sur le total en texte libre du CV, car aucune date
    #   par poste n'était exploitable (ex: CV une-page qui affiche
    #   "3 years of experience" sans dater chaque rôle individuellement).
    # "none" : ni dates ni total déclaré disponibles.
    years_source: Literal["computed", "declared", "none"] = "none"


class SearchFilters(BaseModel):
    semantic_query: str
    min_years_experience: float | None = None
    seniority: Seniority | None = None
    required_industry: str | None = None
    required_keywords: list[str] = Field(default_factory=list)
    preferred_cloud: list[str] = Field(default_factory=list)


class RankedResult(BaseModel):
    cv_id: str
    full_name: str
    source_file: str
    score: float
    explanation: str
