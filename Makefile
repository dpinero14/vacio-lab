PY ?= python
VENV ?= .venv
BIN := $(VENV)/bin
ifeq ($(OS),Windows_NT)
BIN := $(VENV)/Scripts
endif

.PHONY: setup test data notebooks clean

setup:
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -r requirements.txt
	$(BIN)/python -m ipykernel install --user --name vacio-lab --display-name "vacio-lab"

test:
	$(BIN)/python -m pytest -q tests

data:
	$(BIN)/python scripts/download_data.py

notebooks:
	$(BIN)/python -m jupyter nbconvert --to notebook --execute --inplace --ExecutePreprocessor.kernel_name=vacio-lab --ExecutePreprocessor.timeout=3600 notebooks/01_el_mapa_del_vacio.ipynb

clean:
	rm -rf data/processed/*.parquet
