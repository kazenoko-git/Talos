PYTHON ?= python3
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python

.PHONY: help setup check-env

help:
	@echo "make setup      Create local Python environment and install simulation dependencies"
	@echo "make check-env  Check development dependencies (does not run RTL tests)"

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install -r test/requirements.txt

check-env:
	$(VENV_PYTHON) scripts/check_environment.py
