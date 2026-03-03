# Bebliotheca Build System

PYTHON = $(shell command -v guix >/dev/null 2>&1 && echo "guix shell python -- python3" || echo "python3")

.PHONY: all catalog export clean clean-sources import update publish publish-update help test test-structure test-report test-untranslated test-lang test-lang-report test-originals test-originals-report test-metadata test-metadata-report test-all-reports web

all:
	@./build.sh all

catalog:
	@./build.sh catalog

export:
	@./build.sh export

clean:
	@./build.sh clean

clean-sources:
	@./build.sh clean-sources

import:
	@./build.sh import

update:
	@./build.sh update

publish:
	@./build.sh publish

publish-update:
	@./build.sh publish-update

test:
	@$(PYTHON) tests/check_structure.py check --severity error
	@$(PYTHON) tests/check_language.py check
	@$(PYTHON) tests/check_originals.py check
	@$(PYTHON) tests/check_metadata.py check

test-structure:
	@$(PYTHON) tests/check_structure.py check --severity error

test-report:
	@$(PYTHON) tests/check_structure.py report

test-lang:
	@$(PYTHON) tests/check_language.py check

test-lang-report:
	@$(PYTHON) tests/check_language.py report

test-originals:
	@$(PYTHON) tests/check_originals.py check

test-originals-report:
	@$(PYTHON) tests/check_originals.py report

test-metadata:
	@$(PYTHON) tests/check_metadata.py check

test-metadata-report:
	@$(PYTHON) tests/check_metadata.py report

test-all-reports: test-report test-lang-report test-originals-report test-metadata-report

test-untranslated:
	@$(PYTHON) tests/check_structure.py untranslated

web:
	@echo "Starting web server on http://localhost:8080"
	@cd public && python3 -m http.server 8080

help:
	@echo "Bebliotheca Build System"
	@echo ""
	@echo "make                  Clean + catalog + full export"
	@echo "make catalog          Generate catalog.json"
	@echo "make export           Incremental export (changed files only)"
	@echo "make clean            Remove generated HTML + catalog"
	@echo "make clean-sources    Remove auto-generated .org files from all sources"
	@echo "make import           Import content from all source submodules"
	@echo "make update           Update all submodules to latest and re-import"
	@echo "make publish          Import + build + deploy to server"
	@echo "make publish-update   Update sources, build, and deploy"
	@echo "make test             Run all checks (structure + language + originals + metadata)"
	@echo "make test-report      Detailed structure report"
	@echo "make test-lang        Run language placement checks"
	@echo "make test-lang-report Detailed language placement report"
	@echo "make test-originals   Check translations have originals"
	@echo "make test-originals-report Detailed originals report"
	@echo "make test-metadata    Run metadata quality checks"
	@echo "make test-metadata-report Detailed metadata report"
	@echo "make test-all-reports Run all four detailed reports"
	@echo "make test-untranslated List works without translations"
	@echo "make web              Start local web server on port 8080"
	@echo "make help             Show this help"
