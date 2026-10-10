"""Tests du module de parsing : vérifie la logique de bascule texte -> vision
sans dépendre de vrais fichiers CV (fixtures minimales générées à la volée)."""
from pathlib import Path

import fitz  # PyMuPDF

from cvsearch.parsing.extract_text import extract


def _make_text_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    doc.save(path)


def test_pdf_with_enough_text_stays_in_text_mode(tmp_path):
    pdf_path = tmp_path / "cv.pdf"
    _make_text_pdf(pdf_path, "Jane Doe " * 60)  # largement au-dessus du seuil
    result = extract(pdf_path)
    assert result.mode == "text"
    assert len(result.text) > 0


def test_pdf_with_almost_no_text_and_no_images_stays_text_mode(tmp_path):
    # Pas d'image -> même avec peu de texte, pas de bascule vision possible.
    pdf_path = tmp_path / "cv_vide.pdf"
    _make_text_pdf(pdf_path, "A")
    result = extract(pdf_path)
    assert result.mode == "text"
    assert result.image_paths == []
