"""Shared author classification data loaded from authors.json.

Provides lookup functions used by tag_filetags.py, converters, and tests.
The canonical data lives in scripts/authors.json alongside this module.
"""

import json
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

_DATA_PATH = Path(__file__).resolve().parent / 'authors.json'
_CACHE: Optional[dict] = None

CENTURY_RE = re.compile(r'^\d+c-(bc|ad)$')


def load_authors() -> dict:
    """Load and cache authors.json. Returns the full dict."""
    global _CACHE
    if _CACHE is None:
        _CACHE = json.loads(_DATA_PATH.read_text(encoding='utf-8'))
    return _CACHE


def get_author(slug: str) -> Optional[dict]:
    """Look up an author by slug. Returns {'era': ..., 'century': ...} or None."""
    return load_authors()['authors'].get(slug)


def resolve_slug(filepath: Path) -> Tuple[Optional[str], str]:
    """Extract author slug from a filename.

    For 'title--author-slug.org', extracts the slug after '--'.
    For curated files without '--', checks stem_overrides.

    Returns (slug_or_None, stem).
    """
    stem = filepath.stem
    if '--' in stem:
        return stem.rsplit('--', 1)[1], stem
    overrides = load_authors()['stem_overrides']
    return overrides.get(stem), stem


def build_filetags(slug: str) -> Optional[str]:
    """Build a FILETAGS value string from an author slug.

    Returns ':era:century:' or ':era:', or None if slug is unknown.
    """
    author = get_author(slug)
    if author is None:
        return None
    era = author['era']
    century = author.get('century')
    if century:
        return f':{era}:{century}:'
    return f':{era}:'
