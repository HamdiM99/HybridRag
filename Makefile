.PHONY: setup ingest run api ui test smoke eval clean

VENV=.venv
PY=$(VENV)/bin/python
PIP=$(VENV)/bin/pip

setup:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	cp -n .env.example .env || true
	@echo "Editez .env avec vos identifiants APIM avant de continuer."

smoke:
	$(PY) scripts/smoke_test.py

ingest:
	$(PY) scripts/ingest.py data/cvs

api:
	$(VENV)/bin/uvicorn cvsearch.api.main:app --reload --port 8000 --app-dir src

ui:
	$(VENV)/bin/streamlit run src/cvsearch/ui/app.py

eval:
	$(PY) scripts/eval.py

test:
	$(VENV)/bin/pytest -v

clean:
	rm -rf cache index $(VENV) .pytest_cache
