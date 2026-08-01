# Bebliotheca Build System

PYTHON = $(shell command -v guix >/dev/null 2>&1 && echo "guix shell python -- python3" || echo "python3")

.PHONY: all catalog index export clean clean-sources report import update test web help

all:
	@./build.sh all

catalog:
	@./build.sh catalog

index:
	@./build.sh index

export:
	@./build.sh export

clean:
	@./build.sh clean

clean-sources:
	@./build.sh clean-sources

report:
	@./build.sh report

import:
	@./build.sh import

update:
	@./build.sh update

test:
	@$(PYTHON) tests/check_structure.py check --severity error
	@$(PYTHON) tests/check_language.py check
	@$(PYTHON) tests/check_originals.py check
	@$(PYTHON) tests/check_metadata.py check
	@$(PYTHON) tests/check_public_shell.py

web:
	@echo "Starting web server on http://localhost:8080"
	@cd public && python3 -m http.server 8080

help:
	@echo "Bebliotheca Build System"
	@echo ""
	@echo "make                  Clean + catalog + full export"
	@echo "make catalog          Generate catalog.json + index.org files"
	@echo "make index            Generate per-language index.org files"
	@echo "make export           Incremental export (changed files only)"
	@echo "make clean            Remove generated HTML + catalog"
	@echo "make clean-sources    Remove tracked .org files listed in manifests"
	@echo "make report           Write test reports to log/"
	@echo "make import           Import new files from sources (skips existing)"
	@echo "make update           Update all submodules to latest and re-import"
	@echo "make test             Run all checks (structure + language + originals + metadata)"
	@echo "make web              Start local web server on port 8080"
	@echo "make help             Show this help"
