FROM python:3.12-slim

# libgl1 : requis par PyMuPDF pour le rendu de pages en images (fallback vision)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY scripts/ scripts/

ENV PYTHONPATH=/app/src
ENV CACHE_DIR=/app/cache
ENV INDEX_DIR=/app/index

RUN mkdir -p /app/cache /app/index

EXPOSE 8000

CMD ["uvicorn", "cvsearch.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
