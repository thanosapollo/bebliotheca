#!/usr/bin/env python3
"""Static checks for public index shell, 404 page, favicon, and theme markers."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
INDEX = PUBLIC / "index.html"
PAGE_404 = PUBLIC / "404.html"
FAVICON = PUBLIC / "favicon.svg"
CSS = PUBLIC / "themes/src/index_theme/css/index.css"
JS = PUBLIC / "themes/src/index_theme/js/index.js"
CATALOG_GENERATOR = ROOT / "scripts/generate_catalog.py"


def fail(msg: str) -> None:
    print(f"FAIL: {msg}", file=sys.stderr)
    raise SystemExit(1)


def require(path: Path) -> str:
    if not path.is_file():
        fail(f"missing required file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def main() -> None:
    index = require(INDEX)
    page_404 = require(PAGE_404)
    favicon = require(FAVICON)
    css = require(CSS)
    js = require(JS)


    # #1 broken Codeberg link removed
    if "codeberg.org" in index.lower():
        fail("index.html still references Codeberg")
    if "git.thanosapollo.org/bebliotheca" not in index:
        fail("index.html missing Upstream source link")

    # #2 favicon
    if 'rel="icon"' not in index or "favicon.svg" not in index:
        fail("index.html missing favicon link")
    if "<svg" not in favicon:
        fail("favicon.svg is not an SVG document")

    # #3 accessible search name + focus-visible
    if 'for="search-box"' not in index and 'aria-label="Search catalog"' not in index:
        fail("search control lacks accessible name")
    if "Search catalog" not in index:
        fail("search accessible name text missing")
    if "#search-box:focus-visible" not in css:
        fail("CSS missing #search-box:focus-visible")

    # #4 exclusive filter semantics
    if 'role="radiogroup"' not in index:
        fail("filter group missing role=radiogroup")
    if index.count('role="radio"') < 3:
        fail("filter buttons missing role=radio")
    if "aria-checked" not in js or "updateFilterUI" not in js:
        fail("JS missing filter aria-checked updates")

    # #5 branded 404
    if "Return to the library index" not in page_404:
        fail("404.html missing home link copy")
    if 'href="/"' not in page_404:
        fail("404.html missing home href")
    if "Βιβλιοθήκη" not in page_404:
        fail("404.html missing library branding")
    if ".error-page" not in css:
        fail("CSS missing .error-page styles")

    # #8 separate availability and original-language facets
    if "Greek/Latin Only" in index:
        fail("old Greek/Latin Only label still present")
    if "Without English" not in index:
        fail("Without English label missing")
    for value in ('with-en', 'without-en', 'has-gr', 'has-la', 'gr-only', 'la-only'):
        if f'data-filter="{value}"' not in index:
            fail(f"facet value missing: {value}")
        if value not in js:
            fail(f"facet predicate missing: {value}")

    # #7 noscript + fetch failure recovery
    if "<noscript>" not in index:
        fail("index.html missing <noscript> fallback")
    if "catalog-static.html" not in index:
        fail("noscript fallback should link generated static catalog")
    if "showCatalogFailure" not in js:
        fail("JS missing catalog failure recovery helper")
    if "response.ok" not in js:
        fail("JS should reject non-OK catalog responses")
    if "loading.style.display = ''" not in js and 'loading.style.display = ""' not in js:
        fail("showCatalogFailure must restore #loading visibility")
    if "catalogStatus !== 'ready'" not in js:
        fail("applyFilters must no-op until catalog is ready")
    if 'href="catalog.json"' not in js and "href='catalog.json'" not in js:
        fail("failure recovery missing catalog.json link")
    if "git.thanosapollo.org/bebliotheca" not in js:
        fail("failure recovery missing upstream source link")
    if "classList.add('js')" not in index and 'classList.add("js")' not in index:
        fail("index.html must mark html.js so loading/failure can display under JS")
    if ".loading" not in css or "display: none" not in css:
        fail("CSS must hide .loading by default for no-JS")
    if "html.js .loading" not in css:
        fail("CSS must show .loading under html.js")

    # Predicate labels remain exact.
    if "availabilityFilter === 'without-en'" not in js or "hasEnglish" not in js:
        fail("Without English predicate missing")
    if "aria-checked', selected ? 'true' : 'false'" not in js and 'aria-checked", selected ? "true" : "false"' not in js:
        # tolerate either quote style around attribute name
        if "setAttribute('aria-checked'" not in js and 'setAttribute("aria-checked"' not in js:
            fail("filter UI must write exclusive aria-checked state")
        if "selected ? 'true' : 'false'" not in js and 'selected ? "true" : "false"' not in js:
            fail("filter UI must toggle aria-checked true/false exclusively")

    # Ensure gitignore keeps static 404 trackable despite *.html
    gitignore = require(ROOT / ".gitignore")
    if "!public/404.html" not in gitignore:
        fail(".gitignore missing !public/404.html exception")

    # #9-#12 URL state, bounded rendering, preferred titles, semantic controls.
    for marker in (
        "URLSearchParams",
        "window.addEventListener('popstate'",
        "history[mode + 'State']",
        "params.set('q', searchQuery)",
        "params.set('availability', availabilityFilter)",
        "params.set('original', originalFilter)",
        "params.set('page', String(currentPage))",
        "params.get('q')",
        "params.get('availability')",
        "params.get('original')",
        "params.get('page')",
        "function restoreStateFromURL()",
        "function updateURL(mode)",
        "Number.isInteger(page) && page > 0 ? page : 1",
        "selectFacetFromState('availability'",
        "selectFacetFromState('original'",
        "buttons.find(btn => btn.dataset.filter === value) || buttons[0]",
    ):
        if marker not in js:
            fail(f"URL state marker missing: {marker}")
    if 'const PAGE_SIZE = 50' not in js or '.slice(start, start + PAGE_SIZE)' not in js:
        fail("catalog rendering is not bounded")
    if 'class="work-title" href=' not in js:
        fail("preferred title link missing")
    if '<button type="button" class="tag"' not in js or '<button type="button" class="work-author"' not in js:
        fail("author/tag controls must be native buttons")
    if 'id="alphabet-nav"' not in index or 'renderAlphabet' not in js:
        fail("alphabet navigation missing")


    # #18-#21 local icon, landmarks, recovery, static no-JS generation.
    if '<svg class="theme-toggle-icon"' not in index or '☀️' in index or '🌙' in index:
        fail("index theme control must use local restrained SVG")
    if '<main ' not in index or '<footer ' not in index:
        fail("index landmarks missing")
    if 'id="reset-filters"' not in index or 'Reset search and filters' not in index:
        fail("empty/active-state reset control missing")

    spec = importlib.util.spec_from_file_location("generate_catalog", CATALOG_GENERATOR)
    if spec is None or spec.loader is None:
        fail("cannot load catalog generator")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if module.normalize_display_label('Liber 11s · 12s') != 'Liber 11 · Book 12':
        fail("catalog title normalization is not presentation-safe")
    sample = [{
        'title': 'Sample', 'author': 'Author',
        'translations': [
            {'language': 'en', 'title': 'Translation', 'html_path': 'en/sample.html'},
            {'language': 'gr', 'title': 'Πρωτότυπο', 'html_path': 'gr/sample.html'},
        ],
    }]
    with tempfile.TemporaryDirectory() as tmp:
        static_path = Path(tmp) / 'catalog-static.html'
        module.generate_static_catalog(sample, static_path)
        static = require(static_path)
        if 'gr/sample.html' not in static or 'Πρωτότυπο' not in static or '1 of 1 works' not in static:
            fail("static catalog does not derive preferred links from catalog data")

    print("OK: public shell / a11y / fallback checks passed")


if __name__ == "__main__":
    main()
