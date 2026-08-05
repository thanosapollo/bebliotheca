#!/usr/bin/env python3
"""Static checks for public index shell, 404 page, favicon, and theme markers."""

from __future__ import annotations

import importlib.util
import re
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


def _relative_luminance(hex_color: str) -> float:
    raw = hex_color.lstrip("#")
    if len(raw) != 6:
        raise ValueError(f"expected #rrggbb, got {hex_color!r}")
    channels = [int(raw[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]

    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(v) for v in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(foreground: str, background: str) -> float:
    lighter = max(_relative_luminance(foreground), _relative_luminance(background))
    darker = min(_relative_luminance(foreground), _relative_luminance(background))
    return (lighter + 0.05) / (darker + 0.05)


def parse_theme_vars(css: str, selector: str) -> dict[str, str]:
    pattern = re.compile(
        rf"{re.escape(selector)}\s*\{{([^}}]+)\}}",
        re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(css)
    if match is None:
        fail(f"theme block missing: {selector}")
    assert match is not None
    body = match.group(1)
    vars_found: dict[str, str] = {}
    for name, value in re.findall(r"(--[\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", body):
        vars_found[name] = value.lower()
    return vars_found


def assert_contrast(label: str, fg: str, bg: str, minimum: float) -> None:
    ratio = contrast_ratio(fg, bg)
    if ratio + 1e-9 < minimum:
        fail(f"{label}: {fg} on {bg} is {ratio:.2f}:1 (< {minimum}:1)")


def check_catalog_contrast(css: str) -> None:
    dark = parse_theme_vars(css, ':root,\n[data-theme="dark"]')
    light = parse_theme_vars(css, '[data-theme="light"]')

    required = (
        "--bg-primary",
        "--bg-secondary",
        "--bg-tertiary",
        "--text-primary",
        "--text-secondary",
        "--text-muted",
        "--accent-purple",
        "--accent-contrast",
        "--accent-gold",
        "--progress-green",
    )
    for theme_name, theme in (("dark", dark), ("light", light)):
        for key in required:
            if key not in theme:
                fail(f"{theme_name} theme missing {key}")

    # Normal text AA 4.5:1 for body/muted/tags; large-title gold uses 3:1.
    assert_contrast("dark primary text", dark["--text-primary"], dark["--bg-primary"], 4.5)
    assert_contrast("dark secondary text", dark["--text-secondary"], dark["--bg-secondary"], 4.5)
    assert_contrast("dark muted on tertiary (tags)", dark["--text-muted"], dark["--bg-tertiary"], 4.5)
    assert_contrast("dark muted on primary (stats/footer)", dark["--text-muted"], dark["--bg-primary"], 4.5)
    assert_contrast("dark selected filter", dark["--accent-contrast"], dark["--accent-purple"], 4.5)
    assert_contrast("dark purple link", dark["--accent-purple"], dark["--bg-primary"], 4.5)
    assert_contrast("dark gold title (large)", dark["--accent-gold"], dark["--bg-secondary"], 3.0)
    assert_contrast("dark progress label", dark["--progress-green"], dark["--bg-tertiary"], 4.5)
    assert_contrast("dark focus gold UI", dark["--accent-gold"], dark["--bg-primary"], 3.0)

    assert_contrast("light primary text", light["--text-primary"], light["--bg-primary"], 4.5)
    assert_contrast("light secondary text", light["--text-secondary"], light["--bg-secondary"], 4.5)
    assert_contrast("light muted on tertiary (tags)", light["--text-muted"], light["--bg-tertiary"], 4.5)
    assert_contrast("light muted on primary (stats/footer)", light["--text-muted"], light["--bg-primary"], 4.5)
    assert_contrast("light selected filter", light["--accent-contrast"], light["--accent-purple"], 4.5)
    assert_contrast("light purple link", light["--accent-purple"], light["--bg-primary"], 4.5)
    assert_contrast("light gold title (large)", light["--accent-gold"], light["--bg-secondary"], 3.0)
    assert_contrast("light progress label", light["--progress-green"], light["--bg-tertiary"], 4.5)
    assert_contrast("light focus gold UI", light["--accent-gold"], light["--bg-primary"], 3.0)

    for marker in (
        "#search-box:focus-visible",
        ".filter-btn:focus-visible",
        ".tag:focus-visible",
        ".work-author:focus-visible",
        ".alphabet-nav button:focus-visible",
        ".pagination button:focus-visible",
        ".reset-filters:focus-visible",
        ".theme-toggle:focus-visible",
    ):
        if marker not in css:
            fail(f"catalog focus-visible missing: {marker}")


def main() -> None:
    index = require(INDEX)
    page_404 = require(PAGE_404)
    favicon = require(FAVICON)
    css = require(CSS)
    js = require(JS)

    # #19 measured contrast + focus contracts
    check_catalog_contrast(css)


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
        "restoreStateFromURL();\n            applyFilters(false);",
        "window.addEventListener('popstate', function() {\n            restoreStateFromURL();\n            applyFilters(false);\n        });",
        "if (updateHistory) updateURL('push');",
    ):
        if marker not in js:
            fail(f"URL state marker missing: {marker}")
    if "index.js?v=" not in index and "index.js?" not in index:
        fail("index.html must load cache-busted index.js so CDN clients get URL-state JS")
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
    if '<header ' not in index or '<main ' not in index or '<footer ' not in index:
        fail("index landmarks missing (header/main/footer)")
    if 'class="intro"' in index or 'dev-notice' in index:
        fail("source intro must stay out of catalog hierarchy")
    if 'footer-links' not in index or 'git.thanosapollo.org/bebliotheca' not in index:
        fail("quiet source link must live in footer")
    if 'title="Clear search"' not in index or 'title="Use light theme"' not in index:
        fail("icon-only controls need discoverable title tooltips")
    if 'id="reset-filters"' not in index or 'Reset search and filters' not in index:
        fail("empty/active-state reset control missing")
    if "active.push('search" not in js or "reset-filters').hidden = active.length === 0" not in js:
        fail("stats must expose active filter context with reset gate")
    if 'title="Filter by ' not in js or 'aria-label="Filter by ' not in js:
        fail("interactive tags need filter title/aria labels")
    if 'overflow-wrap: anywhere' not in css or '.footer-links' not in css:
        fail("footer links must wrap cleanly on narrow screens")

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
    }, {
        'title': 'Beta', 'author': 'Second',
        'translations': [
            {'language': 'la', 'title': 'Beta Latin', 'html_path': 'la/beta.html'},
        ],
    }]
    # Pad beyond the bound so the static page cannot silently dump the whole catalog.
    for i in range(module.STATIC_CATALOG_LIMIT + 5):
        sample.append({
            'title': f'Pad {i:04d}',
            'author': 'Pad',
            'translations': [
                {'language': 'en', 'title': f'Pad {i:04d}', 'html_path': f'en/pad-{i}.html'},
            ],
        })
    with tempfile.TemporaryDirectory() as tmp:
        static_path = Path(tmp) / 'catalog-static.html'
        module.generate_static_catalog(sample, static_path)
        static = require(static_path)
        if 'gr/sample.html' not in static or 'Πρωτότυπο' not in static:
            fail("static catalog does not prefer Greek original links from catalog data")
        if 'en/sample.html' in static:
            fail("static catalog must not prefer English when Greek exists")
        if f'Showing {module.STATIC_CATALOG_LIMIT} of {len(sample)} works' not in static:
            fail("static catalog must report bounded count from same catalog source")
        if static.count('class="static-author"') != module.STATIC_CATALOG_LIMIT:
            fail("static catalog work rows must match STATIC_CATALOG_LIMIT")
        if f'en/pad-{module.STATIC_CATALOG_LIMIT}.html' in static:
            fail("static catalog silently exceeded STATIC_CATALOG_LIMIT")
        if 'static-letter-nav' not in static or 'id="letter-Π"' not in static:
            fail("static catalog missing letter jump navigation")
        if f'index.css?v={module.INDEX_CSS_CACHE_BUST}' not in static:
            fail("static catalog CSS cache-bust must follow generator constant")
        if f'index.css?v={module.INDEX_CSS_CACHE_BUST}' not in index:
            fail("index.html CSS cache-bust drifted from generator constant")
        if f'index.css?v={module.INDEX_CSS_CACHE_BUST}' not in require(PAGE_404):
            fail("404.html CSS cache-bust drifted from generator constant")
        if '.static-catalog' not in css or '.static-letter-nav' not in css:
            fail("index.css missing static catalog presentation rules")
        if "static_output_path: Optional[Path] = None" not in require(CATALOG_GENERATOR):
            fail("catalog generator must accept static_output_path")
        if "static_output_path=args.static_output" not in require(CATALOG_GENERATOR):
            fail("catalog CLI must always emit static catalog path")

    print("OK: public shell / a11y / fallback checks passed")


if __name__ == "__main__":
    main()
