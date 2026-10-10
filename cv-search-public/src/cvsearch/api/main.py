"""API FastAPI : ingestion de CV, recherche en langage naturel, consultation.

Fonctionnalités minimales : ingestion, requête en langage naturel,
affichage des résultats. Endpoints supplémentaires (`/cvs/{id}`, `/health`)
pour l'exploitation et le débogage.
"""
import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from pydantic import BaseModel

from cvsearch.pipeline import get_store, ingest_file, search
from cvsearch.schema import CVProfile, RankedResult

app = FastAPI(
    title="CV Search",
    description="Mini système de gestion et de recherche de CV pour une équipe RH.",
    version="0.1.0",
)


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


class SearchResponse(BaseModel):
    query: str
    results: list[RankedResult]


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "indexed_cvs": len(get_store().profiles)}


@app.post("/cvs", response_model=CVProfile)
async def upload_cv(file: UploadFile) -> CVProfile:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx", ".pptx"}:
        raise HTTPException(400, f"Format non supporté : {suffix}")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        profile = ingest_file(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    return profile


@app.get("/cvs/{cv_id}", response_model=CVProfile)
def get_cv(cv_id: str) -> CVProfile:
    store = get_store()
    profile = store.profiles.get(cv_id)
    if profile is None:
        raise HTTPException(404, "CV introuvable")
    return profile


@app.get("/cvs", response_model=list[CVProfile])
def list_cvs() -> list[CVProfile]:
    return list(get_store().profiles.values())


@app.post("/search", response_model=SearchResponse)
def run_search(request: SearchRequest) -> SearchResponse:
    results = search(request.query, top_k=request.top_k)
    return SearchResponse(query=request.query, results=results)
