"""Lecture d'un CV par image quand l'extraction texte est insuffisante.

Cas typique : un CV Word/PDF dont tout le corps (expériences, dates) est une
image collée dans le document plutôt que du texte natif. gpt-5 accepte des
entrées image, donc on lui fournit directement les pages/images plutôt que de
dépendre d'un service OCR supplémentaire.
"""
import base64
from pathlib import Path


def _to_data_url(path: Path) -> str:
    data = path.read_bytes()
    b64 = base64.b64encode(data).decode("ascii")
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64,{b64}"


def build_vision_content(text_hint: str, image_paths: list[Path]) -> list[dict]:
    """Construit le contenu multimodal (texte + images) pour l'appel chat."""
    content: list[dict] = []
    if text_hint.strip():
        content.append(
            {
                "type": "text",
                "text": (
                    "Texte partiellement extrait automatiquement (peut être "
                    f"incomplet, ex: seulement l'en-tête) :\n{text_hint.strip()}"
                ),
            }
        )
    for img_path in image_paths:
        content.append({"type": "image_url", "image_url": {"url": _to_data_url(img_path)}})
    return content
