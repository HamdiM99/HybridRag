"""Interface Streamlit minimale : upload de CV + recherche en langage naturel.

Lancer avec `make ui` (ou `streamlit run src/cvsearch/ui/app.py`).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # src/ sur le path

import streamlit as st

from cvsearch.pipeline import get_store, ingest_file, search

st.set_page_config(page_title="CV Search", layout="wide")
st.title("Recherche de CV — équipe RH")

with st.sidebar:
    st.header("Ingestion")
    uploaded = st.file_uploader("Déposer un CV", type=["pdf", "docx", "pptx"])
    if uploaded and st.button("Indexer ce CV"):
        tmp_path = Path("cache") / uploaded.name
        tmp_path.parent.mkdir(exist_ok=True)
        tmp_path.write_bytes(uploaded.getvalue())
        with st.spinner("Extraction et indexation..."):
            profile = ingest_file(tmp_path)
        st.success(f"CV indexé : {profile.full_name} (mode: {profile.parsing_mode})")

    store = get_store()
    st.metric("CV indexés", len(store.profiles))

query = st.text_input(
    "Requête en langage naturel",
    placeholder="ex: Data Scientist senior avec expérience en IA générative et déploiement cloud",
)

if query:
    with st.spinner("Recherche en cours..."):
        results = search(query, top_k=5)

    if not results:
        st.warning("Aucun profil ne correspond à cette requête (filtres ou pertinence insuffisante).")
    else:
        for r in results:
            with st.container(border=True):
                st.subheader(f"{r.full_name} — score {r.score:.0f}/100")
                st.write(r.explanation)
                st.caption(r.source_file)
