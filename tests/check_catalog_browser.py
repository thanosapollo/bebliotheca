#!/usr/bin/env python3
"""Headless search-first journeys against a running static preview.

Run: uv run --with playwright python tests/check_catalog_browser.py [URL]
Uses local Chromium (or CHROMIUM); no global dependencies or generated files.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright

BASE = (sys.argv[1] if len(sys.argv) > 1 else os.environ.get("CATALOG_URL", "http://127.0.0.1:8765/")).rstrip("/") + "/"


def params(page):
    return parse_qs(urlparse(page.url).query)


def settle(page):
    # Deliberately pass the debounce boundary to expose delayed stale writes.
    page.wait_for_timeout(250)


def fixture_work(work_id, title, author="Writer", **metadata):
    return {"id": work_id, "title": title, "author": author, **metadata,
            "translations": [{"language": "gr", "language_name": "Greek", "html_path": f"gr/{work_id}.html",
                              "title": title, "author": author}]}


def check_search_fixtures(new_page):
    ranking = [fixture_work("substring", "A Sundial Moonrise"),
               fixture_work("phrase", "B Notes on Sun Moon"),
               fixture_work("tokens", "C Moon and Sun"),
               fixture_work("exact-b", "Ω"), fixture_work("exact-a", "Ω"),
               fixture_work("author-only", "A Treatise", author="Sun Moon")]
    for work in ranking[3:5]:
        work["translations"].append({"language": "en", "title": "The Sun Moon", "author": "Writer",
                                     "html_path": "en/translation.html"})
    page = new_page()
    page.route("**/catalog.json", lambda route: route.fulfill(json={"works": ranking}))
    page.goto(BASE)
    expect(page.locator(".work-item")).to_have_count(len(ranking))
    ids = lambda: page.locator(".work-item").evaluate_all("els=>els.map(el=>el.dataset.workId)")
    assert ids() == ["substring", "author-only", "phrase", "tokens", "exact-a", "exact-b"]
    page.locator("#search-box").fill("sun moon")
    settle(page)
    assert ids() == ["exact-a", "exact-b", "phrase", "tokens", "substring", "author-only"]
    expect(page.locator("#search-dropdown [role=option]").filter(has_text="Work ·").first).to_contain_text("The Sun Moon")
    page.locator("#search-clear").click()
    assert ids() == ["substring", "author-only", "phrase", "tokens", "exact-a", "exact-b"]
    page.context.close()

    aliases = [fixture_work("alpha-one", "First", "Shared Name", author_id="alpha", author_aliases=["Shared Name", "Ποιητής", "First Writer"]),
               fixture_work("alpha-two", "Second", "Ποιητής", author_id="alpha", author_aliases=["Shared Name", "Ποιητής", "First Writer"]),
               fixture_work("beta", "Third", "Shared Name", author_id="beta", author_aliases=["Shared Name", "Second Writer"]),
               fixture_work("legacy", "Fourth", "Shared Name", author_latin="Legacy Writer")]
    aliases[0]["translations"].append({"language": "en", "title": "First", "author": "Translator instrumentation", "html_path": "en/first.html"})
    page = new_page()
    page.route("**/catalog.json", lambda route: route.fulfill(json={"works": aliases}))
    for query in ("ποιητης", "First Writer"):
        page.goto(BASE + "?" + urlencode({"q": query}))
        expect(page.locator(".work-item")).to_have_count(2)
        assert set(page.locator(".work-item").evaluate_all("els=>els.map(el=>el.dataset.workId)")) == {"alpha-one", "alpha-two"}
    page.goto(BASE + "?q=Shared")
    expect(page.locator(".work-item")).to_have_count(4)
    page.locator("#search-box").focus()
    options = page.locator("#search-dropdown [role=option]").filter(has_text="Author ·")
    expect(options).to_have_count(3)
    options.filter(has_text="2 works").click()
    settle(page)
    assert params(page)["author_id"] == ["alpha"]
    expect(page.locator(".work-item")).to_have_count(2)
    page.goto(BASE + "?author=Shared+Name&author_id=beta")
    expect(page.locator(".work-item")).to_have_count(1)
    expect(page.locator(".work-item")).to_have_attribute("data-work-id", "beta")
    page.locator(".work-author").click()
    assert params(page)["author_id"] == ["beta"]
    page.reload()
    expect(page.locator(".work-item")).to_have_attribute("data-work-id", "beta")
    page.goto(BASE + "?author=Wrong+Writer&author_id=alpha")
    expect(page.locator(".work-item")).to_have_count(2)
    expect(page.get_by_role("group", name="Current search")).to_contain_text("Author: Shared Name")
    expect(page.locator("#search-context")).not_to_contain_text("Wrong Writer")
    page.goto(BASE + "?author=Wrong+Writer&author_id=missing")
    expect(page.locator(".no-results")).to_be_visible()
    expect(page.locator("#search-context")).to_contain_text("Author: missing")
    expect(page.locator("#search-context")).not_to_contain_text("Wrong Writer")
    page.goto(BASE + "?work=legacy")
    expect(page.locator(".work-item")).to_have_count(1)
    page.locator(".work-author").click()
    expect(page.locator(".work-item")).to_have_count(1)
    expect(page.locator(".work-item")).to_have_attribute("data-work-id", "legacy")
    page.reload()
    expect(page.locator(".work-item")).to_have_attribute("data-work-id", "legacy")
    page.goto(BASE + "?q=Translator")
    expect(page.locator(".no-results")).to_be_visible()
    page.locator("#search-box").focus()
    expect(page.locator("#search-dropdown")).to_be_hidden()
    # An old catalog without canonical metadata retains primary-name/Latin-name URLs.
    aliases[:] = [fixture_work("legacy", "An old work", "Ποιητής", author_latin="Legacy Writer")]
    for author in ("Ποιητής", "Legacy Writer"):
        page.goto(BASE + "?" + urlencode({"author": author}))
        expect(page.locator(".work-item")).to_have_count(1)
    page.goto(BASE + "?q=Legacy")
    expect(page.locator(".work-item")).to_have_count(1)
    page.locator("#search-box").focus()
    page.locator("#search-dropdown [role=option]").first.click()
    assert "author_id" not in params(page)
    expect(page.locator(".work-item")).to_have_count(1)
    page.context.close()
    print("PASS fixtures: title relevance/ties/no-query order, canonical collisions, primary aliases, old catalogs")


def main():
    with urlopen(BASE + "catalog.json") as response:
        real_catalog = json.load(response)
    works = real_catalog["works"]
    paths = [trans["html_path"] for work in works for trans in work["translations"]]
    assert any(not path.isascii() for path in paths), "Real catalog must exercise Unicode filenames"
    def assert_plato_results(page):
        ids = page.locator(".work-item").evaluate_all("els=>els.map(el=>el.dataset.workId)")
        assert ids
        for work_id in ids:
            work = next(work for work in works if work["id"] == work_id)
            text = " ".join([work.get("author", ""), work.get("author_latin", ""), work["title"]] +
                            [t.get(field, "") for t in work["translations"] for field in ("title", "author")])
            assert "plato" in text.lower(), work_id
    with sync_playwright() as playwright:
        executable = os.environ.get("CHROMIUM") or shutil.which("chromium") or shutil.which("chromium-browser")
        browser = playwright.chromium.launch(executable_path=executable, headless=True, args=["--no-sandbox"])
        errors = []

        def new_page(**options):
            context = browser.new_context(**options)
            # Fonts must not make the behavior suite depend on Google's availability.
            context.route("https://fonts.googleapis.com/**", lambda route: route.fulfill(status=200, body=""))
            context.route("https://fonts.gstatic.com/**", lambda route: route.abort())
            page = context.new_page()
            page.on("pageerror", lambda error: errors.append(str(error)))
            return page

        failures = []
        for journey in ("known title", "Greek author", "new query"):
            probe = new_page()
            try:
                if journey == "known title":
                    for query, work_id in (("Iliad", "iliad--homer"), ("Homer Iliad", "iliad--homer"), ("Plato Republic", "republic--plato")):
                        probe.goto(BASE + "?" + urlencode({"q": query}))
                        expect(probe.locator(".work-item").first).to_have_attribute("data-work-id", work_id)
                        probe.locator("#search-box").focus()
                        expect(probe.locator("#search-dropdown [role=option]").filter(has_text="Work ·").first).to_contain_text(query.split()[-1])
                elif journey == "Greek author":
                    probe.goto(BASE + "?" + urlencode({"q": "ομηρος"}))
                    expect(probe.locator('.work-item[data-work-id="iliad--homer"]')).to_have_count(1)
                    greek_ids = probe.locator(".work-item").evaluate_all("els=>els.map(el=>el.dataset.workId).sort()")
                    probe.locator("#search-box").fill("Homer")
                    settle(probe)
                    english_ids = probe.locator(".work-item").evaluate_all("els=>els.map(el=>el.dataset.workId).sort()")
                    assert set(greek_ids) <= set(english_ids), "English may additionally match commentary titles"
                    probe.locator("#search-dropdown [role=option]").filter(has_text="Author ·").first.click()
                    settle(probe)
                    assert probe.locator(".work-item").evaluate_all("els=>els.map(el=>el.dataset.workId).sort()") == greek_ids
                    probe.goto(BASE + "?" + urlencode({"q": "ομηρος"}))
                    expect(probe.locator('.work-item[data-work-id="iliad--homer"]')).to_have_count(1)
                    probe.locator("#search-box").focus()
                    options = probe.locator("#search-dropdown [role=option]").filter(has_text="Author ·")
                    expect(options).to_have_count(1)
                    options.click()
                    settle(probe)
                    assert params(probe)["author_id"] == ["homer"]
                    assert probe.locator(".work-item").evaluate_all("els=>els.map(el=>el.dataset.workId).sort()") == greek_ids
                    expect(probe.locator('.work-item[data-work-id="homeric-epigrams"] .work-author')).to_have_text("Ὅμηρος")
                    probe.reload()
                    expect(probe.locator('.work-item[data-work-id="iliad--homer"]')).to_have_count(1)
                else:
                    probe.goto(BASE + "?work=gorgias--plato")
                    expect(probe.locator(".work-item")).to_have_count(1)
                    probe.locator("#search-box").fill("Iliad")
                    expect(probe.locator("#search-dropdown [role=option]").first).to_contain_text("Iliad")
                    settle(probe)
                    expect(probe.locator(".work-item").first).to_have_attribute("data-work-id", "iliad--homer")
                    assert "work" not in params(probe)
                    expect(probe.locator('#search-context [data-remove="work"]')).to_have_count(0)
                    probe.goto(BASE + "?author=Plato&work=gorgias--plato&lang=en&collection=classical")
                    expect(probe.locator(".work-item")).to_have_count(1)
                    probe.locator("#search-box").fill("Republic")
                    expect(probe.locator("#search-dropdown [role=option]").first).to_contain_text("Republic")
                    settle(probe)
                    assert params(probe) == {"q": ["Republic"], "author": ["Plato"], "lang": ["en"], "collection": ["classical"]}
                    expect(probe.locator('.work-item[data-work-id="republic--plato"]')).to_have_count(1)
                print("PASS search regression: " + journey)
            except AssertionError as error:
                failures.append(journey + ": " + str(error))
            finally:
                probe.context.close()
        assert not failures, "\n".join(failures)
        check_search_fixtures(new_page)

        page = new_page(viewport={"width": 1280, "height": 900})
        page.goto(BASE)
        expect(page.locator(".work-item")).to_have_count(50)
        expect(page.locator("#stats-text")).to_contain_text(f"{len(works):,} works")
        assert not page.locator("#search-options").evaluate("el => el.open")
        assert page.locator(".work-tags, .alphabet-nav, [role=radio]").count() == 0
        assert page.locator("a.work-title").count() == 0
        expect(page.locator("#works-container")).to_have_attribute("aria-busy", "false")
        print(f"PASS real catalog: {len(works)} works, all {len(paths)} reader paths validated, 50-row DOM")

        search = page.locator("#search-box")
        search.fill("Plato")
        expect(page.locator("#search-dropdown").get_by_role("option").first).to_contain_text("Author")
        expect(search).to_have_attribute("aria-expanded", "true")
        assert page.locator("#search-dropdown").get_by_role("option").count() <= 8
        search.press("ArrowDown")
        expect(search).to_have_attribute("aria-activedescendant", "suggestion-0")
        expect(page.locator("#suggestion-0")).to_have_attribute("aria-selected", "true")
        search.press("Tab")
        assert page.evaluate("document.activeElement.id") != "search-box"
        assert "author" not in params(page), "Tab must not select"
        search.focus()
        search.press("ArrowUp")
        assert search.get_attribute("aria-activedescendant")
        search.press("Escape")
        expect(search).to_have_attribute("aria-expanded", "false")
        expect(search).to_have_value("Plato")
        search.press("ArrowDown")
        search.press("Enter")
        settle(page)
        assert params(page)["author"] == ["Plato"] and "q" not in params(page)
        expect(search).to_have_value("")
        assert all(name == "Plato" for name in page.locator(".work-author").all_text_contents())
        search.fill("gorg")
        expect(page.locator("#search-dropdown").get_by_role("option").first).to_contain_text("Gorgias")
        page.locator("#search-dropdown").get_by_role("option").first.click()
        settle(page)
        assert params(page)["work"] == ["gorgias--plato"]
        expect(page.locator(".work-item")).to_have_count(1)
        assert page.locator(".lang-btn").all_text_contents() == ["Ἑλληνικά", "English"]
        assert urlparse(page.url).path == "/", "Work selection must not choose a reader language"
        work_url = page.url
        page.reload()
        expect(page.locator(".work-item")).to_have_count(1)
        assert page.url == work_url
        page.locator('#search-context [data-remove="work"]').click()
        search.fill("gorgias")
        settle(page)
        expect(page.locator(".work-item")).to_have_count(1)
        assert params(page)["author"] == ["Plato"]
        print("PASS ranked author/work suggestions, arrows/Enter/Escape/ordinary Tab, click, author narrowing, reload")

        page.locator("#reset-filters").click()
        search.fill("Plato lang:")
        expect(page.locator("#search-dropdown").get_by_role("option").filter(has_text="English")).to_have_count(1)
        page.locator("#search-dropdown").get_by_role("option").filter(has_text="English").click()
        settle(page)
        assert params(page)["q"] == ["Plato lang:en"]
        assert_plato_results(page)
        search.fill("Plato #class")
        page.locator("#search-dropdown").get_by_role("option").filter(has_text="#classical").click()
        settle(page)
        assert params(page)["q"] == ["Plato #classical"]
        search.fill("Γοργιας")
        settle(page)
        assert "gorgias--plato" in page.locator(".work-item").evaluate_all("els=>els.map(el=>el.dataset.workId)")
        page.locator("#reset-filters").click()
        search.fill("English")
        page.locator("#search-dropdown").get_by_role("option").filter(has_text="Reading language").click()
        assert params(page)["lang"] == ["en"]
        page.locator("#search-options summary").click()
        page.locator("#collection-filter").select_option("patristic")
        assert params(page)["collection"] == ["patristic"]
        for work_id in page.locator(".work-item").evaluate_all("els=>els.map(el=>el.dataset.workId)"):
            work = next(work for work in works if work["id"] == work_id)
            assert "patristic" in work["tags"] and any(t["language"] == "en" for t in work["translations"])
        print("PASS Greek normalization, compound #tag/lang: suggestions preserve words, contextual narrowing")

        for availability in ("with-en", "without-en"):
            for original in ("has-gr", "has-la"):
                page.goto(BASE + "?" + urlencode({"availability": availability}))
                expect(page.locator("#works-container")).to_have_attribute("aria-busy", "false")
                page.locator("#search-options summary").click()
                expect(page.locator("#original-filter option")).to_have_text(["Any", "Greek", "Latin"])
                page.locator("#original-filter").select_option(original)
                assert params(page)["original"] == [original]
                expected = []
                for work in works:
                    langs = {t["language"] for t in work["translations"]}
                    if not langs & {"gr", "la"} or (("en" in langs) != (availability == "with-en")):
                        continue
                    if original == "has-gr" and "gr" not in langs or original == "has-la" and "la" not in langs:
                        continue
                    expected.append(work)
                expect(page.locator("#stats-text")).to_contain_text(f"{len(expected):,} work")
                assert page.locator(".work-item").count() == min(50, len(expected))
        for legacy, current in (("gr-only", "has-gr"), ("la-only", "has-la")):
            page.goto(BASE + "?original=" + legacy)
            expect(page.locator("#works-container")).to_have_attribute("aria-busy", "false")
            expect(page.locator("#original-filter")).to_have_value(current)
        print("PASS plain Any/Greek/Latin choices, live filtering and legacy language links")
        page.goto(BASE + "?page=999999&original=not-valid")
        expect(page.locator("#works-container")).to_have_attribute("aria-busy", "false")
        expect(page.locator("#next-page")).to_be_disabled()
        assert page.locator(".work-item").count() <= 50
        page.goto(BASE)
        expect(page.locator(".work-item")).to_have_count(50)
        first_ids = page.locator(".work-item").evaluate_all("els=>els.map(el=>el.dataset.workId)")
        page.locator("#next-page").click()
        assert params(page)["page"] == ["2"]
        assert page.locator(".work-item").evaluate_all("els=>els.map(el=>el.dataset.workId)") != first_ids
        assert page.locator(".work-title").first.evaluate("el=>el===document.activeElement")
        page.go_back()
        expect(page.locator("#page-status")).to_have_text("Page 1 of " + str((len(works) + 49) // 50))
        assert page.locator(".work-item").evaluate_all("els=>els.map(el=>el.dataset.workId)") == first_ids
        search.fill("Plato")
        settle(page)
        search.fill("Aristotle")
        page.go_back()
        restored_url = page.url
        settle(page)
        assert page.url == restored_url and search.input_value() == params(page).get("q", [""])[0]
        page.goto(BASE + "?q=Plato")
        expect(page.locator(".work-item").first).to_be_visible()
        search.fill("Aristotle")
        page.locator("#reset-filters").click()
        settle(page)
        assert not params(page) and search.input_value() == ""
        search.fill("zzzz-no-such-work")
        settle(page)
        expect(page.locator(".no-results")).to_contain_text("No works found")
        expect(page.locator("#reset-filters")).to_be_visible()
        page.locator("#reset-filters").click()
        expect(page.locator(".work-item")).to_have_count(50)
        print("PASS original-language/availability combinations, bounded pagination, invalid page clamp, Back/debounce/reset/empty")

        page.goto(BASE + "?work=gorgias--plato")
        expect(page.locator(".work-item")).to_have_count(1)
        page.locator('.lang-btn[href="en/gorgias--plato.html"]').click()
        page.wait_for_url("**/en/gorgias--plato.html")
        assert page.locator("body").inner_text().strip()
        page.go_back()
        expect(page.locator(".work-item")).to_have_count(1)
        assert params(page)["work"] == ["gorgias--plato"]
        assert page.evaluate("JSON.parse(localStorage.getItem('recentlyViewed'))['gorgias--plato']")
        page.evaluate("localStorage.setItem('bebliotheca_reading_progress', JSON.stringify({'/en/gorgias--plato.html':{percentage:42,timestamp:'2026-01-01T12:00:00Z'}}))")
        page.reload()
        expect(page.locator(".reading-progress")).to_have_text("42% read")
        page.locator("#theme-toggle").click()
        expect(page.locator("html")).to_have_attribute("data-theme", "light")
        page.reload()
        expect(page.locator("html")).to_have_attribute("data-theme", "light")
        for width in (390, 320):
            page.set_viewport_size({"width": width, "height": 844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
            search.fill("Plato")
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        print("PASS explicit English reader and Back, reading progress, persistent theme, 390/320px reflow")

        blocked = new_page()
        blocked.add_init_script("Object.defineProperty(window, 'localStorage', {get() {throw new DOMException('blocked', 'SecurityError')}})")
        blocked.goto(BASE + "?q=Plato")
        expect(blocked.locator(".work-item").first).to_be_visible()
        blocked.locator("#theme-toggle").click()
        expect(blocked.locator("html")).to_have_attribute("data-theme", "light")
        blocked.get_by_role("button", name="Find works by Plato", exact=True).first.click()
        expect(blocked.locator("#search-context")).to_contain_text("Plato")

        delayed = new_page()
        held = []
        delayed.route("**/catalog.json", lambda route: held.append(route))
        delayed.goto(BASE + "?q=Aristotle", wait_until="domcontentloaded")
        expect(delayed.locator("#loading")).to_be_visible()
        delayed.locator("#search-box").fill("Plato")
        delayed.wait_for_timeout(500)
        assert held
        held.pop().fulfill(json=real_catalog)
        expect(delayed.locator(".work-item").first).to_be_visible()
        settle(delayed)
        expect(delayed.locator("#search-box")).to_have_value("Plato")
        assert_plato_results(delayed)
        assert params(delayed)["q"] == ["Plato"]
        delayed.unroute("**/catalog.json")
        delayed.reload()
        expect(delayed.locator(".work-item").first).to_be_visible()
        expect(delayed.locator("#search-box")).to_have_value("Plato")
        assert_plato_results(delayed)

        failed = new_page()
        failed.route("**/catalog.json", lambda route: route.fulfill(status=503, body="unavailable"))
        failed.goto(BASE)
        expect(failed.locator("#retry-catalog")).to_be_visible()
        failed.locator("#search-box").fill("Plato")
        settle(failed)
        expect(failed.locator("#stats-text")).to_have_text("Catalog unavailable")
        failed.unroute("**/catalog.json")
        failed.locator("#retry-catalog").click()
        expect(failed.locator(".work-item").first).to_be_visible()
        assert_plato_results(failed)
        print("PASS denied storage, input during delayed load, HTTP failure and retry preserving query")

        fixture = {"works": [{"id": "unicode", "title": '<img src=x onerror="window.pwned=1">', "author": 'Author " & <script>',
            "tags": ["classical"], "translations": [{"language": "gr", "language_name": "Greek", "html_path": "gr/ἐξήγησις.html", "title": '<img src=x onerror="window.pwned=1">', "author": 'Author " & <script>'}]}]}
        safe = new_page()
        safe.route("**/catalog.json", lambda route: route.fulfill(json=fixture))
        safe.goto(BASE)
        expect(safe.locator(".work-title")).to_have_text(fixture["works"][0]["title"])
        assert not safe.locator("#works-container img, #works-container script").count()
        assert safe.locator(".lang-btn").get_attribute("href") == "gr/ἐξήγησις.html"
        safe.locator("#search-box").fill("Author")
        expect(safe.locator("#search-dropdown").get_by_role("option").first).to_contain_text('Author " & <script>')
        expect(safe.locator("#search-dropdown .suggestion-desc").first).to_have_text("Author · 1 work")
        assert not safe.locator("#search-dropdown script").count()
        for bad_path in ("javascript:alert(1)", "//example.com/x.html", "gr/../en/x.html", "gr/%2e%2e/x.html", "gr/evil.html?x=1"):
            fixture["works"][0]["translations"][0]["html_path"] = bad_path
            safe.reload()
            expect(safe.locator("#retry-catalog")).to_be_visible()
            assert not safe.locator(".lang-btn").count()
        nojs = new_page(java_script_enabled=False)
        nojs.goto(BASE)
        expect(nojs.locator('.fallback-notice a[href="catalog-static.html"]')).to_be_visible()
        expect(nojs.locator("#loading")).not_to_be_visible()
        expect(nojs.locator(".catalog-search")).not_to_be_visible()
        nojs.goto(BASE + "404.html")
        expect(nojs.get_by_role("link", name="Return to the library index")).to_be_visible()
        print("PASS Unicode/XSS fixtures, unsafe links rejected, noscript and 404 preserved")
        assert not errors, errors
        browser.close()
        print("OK: all search-first browser journeys passed (Chromium, no screen-reader claim)")


if __name__ == "__main__":
    main()
