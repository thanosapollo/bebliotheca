#!/usr/bin/env python3
"""Focused reader presentation and build-metadata checks."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
READER_JS = PUBLIC / "themes/src/readtheorg_theme/js/readtheorg.js"
PARALLEL_JS = PUBLIC / "themes/src/readtheorg_theme/js/readtheorg-parallel.js"
READER_CSS = PUBLIC / "themes/src/readtheorg_theme/css/readtheorg.css"
EXPORT_EL = ROOT / "build-export.el"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def require(path: Path) -> str:
    if not path.is_file():
        fail(f"missing {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def main() -> None:
    reader_js = require(READER_JS)
    parallel_js = require(PARALLEL_JS)
    reader_css = require(READER_CSS)
    export_el = require(EXPORT_EL)

    if 'hide side TOC by default' not in reader_css or '#table-of-contents:target' not in reader_css:
        fail("mobile TOC collapse contract missing")
    if 'parallel-pane-reader' not in reader_js or 'body.parallel-pane-reader #table-of-contents' not in reader_css:
        fail("parallel pane chrome suppression missing")
    if 'normalizeDisplayText' not in reader_js or "'Book $1'" not in reader_js:
        fail("cryptic reader display-label normalization missing")
    if 'bebliotheca-languages' not in export_el or 'bebliotheca-languages' not in parallel_js:
        fail("build-time reader language metadata missing")
    if "type: 'HEAD'" in parallel_js or 'type: "HEAD"' in parallel_js:
        fail("parallel reader still performs HEAD probes")

    with tempfile.TemporaryDirectory() as tmp:
        project = Path(tmp)
        for language in ("la", "en"):
            source = project / "content" / language / "sample.org"
            source.parent.mkdir(parents=True)
            source.write_text(
                "#+TITLE: Sample 11s\n"
                f"#+EXPORT_FILE_NAME: ../../public/{language}/sample.html\n\n"
                "* 11s\nText.\n",
                encoding="utf-8",
            )
        result = subprocess.run(
            [
                "emacs", "--batch", "-Q", "--load", str(EXPORT_EL), "--",
                "content/la/sample.org", "content/en/sample.org",
            ],
            cwd=project,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            fail(f"reader export failed: {result.stderr.strip()}")
        for language in ("la", "en"):
            output = project / "public" / language / "sample.html"
            html = output.read_text(encoding="utf-8")
            if 'name="bebliotheca-languages" content="la,en"' not in html:
                fail(f"language metadata missing from {language} export")

    print("OK: reader shell / build metadata checks passed")


if __name__ == "__main__":
    main()
