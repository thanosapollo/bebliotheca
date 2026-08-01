#!/usr/bin/env python3
"""Static checks for public index shell, 404 page, favicon, and theme markers."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
INDEX = PUBLIC / "index.html"
PAGE_404 = PUBLIC / "404.html"
FAVICON = PUBLIC / "favicon.svg"
CSS = PUBLIC / "themes/src/index_theme/css/index.css"
JS = PUBLIC / "themes/src/index_theme/js/index.js"


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

    # #6 rename only
    if "Greek/Latin Only" in index:
        fail("old Greek/Latin Only label still present")
    if "Without English" not in index:
        fail("Without English label missing")
    if 'data-filter="untranslated"' not in index:
        fail("untranslated filter data attribute missing")
    if "translationFilter === 'untranslated'" not in js:
        fail("untranslated predicate missing from JS")

    # #7 noscript + fetch failure recovery
    if "<noscript>" not in index:
        fail("index.html missing <noscript> fallback")
    if "catalog.json" not in index:
        fail("noscript fallback should mention catalog.json")
    if "showCatalogFailure" not in js:
        fail("JS missing catalog failure recovery helper")
    if "response.ok" not in js:
        fail("JS should reject non-OK catalog responses")

    # Ensure gitignore keeps static 404 trackable despite *.html
    gitignore = require(ROOT / ".gitignore")
    if "!public/404.html" not in gitignore:
        fail(".gitignore missing !public/404.html exception")

    print("OK: public shell / a11y / fallback checks passed")


if __name__ == "__main__":
    main()
