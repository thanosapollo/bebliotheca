#!/usr/bin/env python3
"""Generate per-language index.org files for Emacs navigation.

Creates content/{gr,en,la}/index.org with org-mode headings grouped by
era and author, with file links for easy navigation via C-c C-o.

Usage:
    python3 scripts/generate_index.py
    python3 scripts/generate_index.py --quiet
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add scripts/ to path for author_data import
sys.path.insert(0, str(Path(__file__).resolve().parent))
import author_data

ERA_ORDER = ['classical', 'imperial', 'patristic', 'byzantine', 'scripture']
ERA_LABELS = {
    'classical': 'Κλασικά - Classical',
    'imperial': 'Αὐτοκρατορικά - Imperial',
    'patristic': 'Πατερικά - Patristic',
    'byzantine': 'Βυζαντινά - Byzantine',
    'scripture': 'Ἁγία Γραφή - Scripture',
}

LANG_TITLES = {
    'gr': 'Ἑλληνικά',
    'en': 'English',
    'la': 'Latina',
}

MANIFESTS = {
    'log/perseus-manifest.txt': 'perseus',
    'log/latinlit-manifest.txt': 'perseus',
    'log/apostolic-manifest.txt': 'apostolic',
    'log/pg-migne-manifest.txt': 'pg_migne',
}


def load_manifests(root: Path) -> Dict[str, str]:
    """Load manifest files => {relative_path: source_name}."""
    result = {}
    for rel, source in MANIFESTS.items():
        path = root / rel
        if not path.exists():
            continue
        for line in path.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if line:
                result[line] = source
    return result


def load_pg_greek_names(root: Path) -> Dict[str, str]:
    """Load Greek author names from PG Migne authors.py => {slug: greek_name}."""
    path = root / 'sources' / 'pg-migne' / 'authors.py'
    if not path.exists():
        return {}
    ns = {}
    try:
        exec(path.read_text(encoding='utf-8'), ns)
    except Exception:
        return {}
    result = {}
    for entry in ns.get('AUTHORS', {}).values():
        slug = entry.get('slug', '')
        name = entry.get('greek_name', '')
        if slug and name and slug not in result:
            result[slug] = name
    return result


def parse_header(filepath: Path) -> Optional[Dict[str, str]]:
    """Extract TITLE and AUTHOR from org file header (first 50 lines)."""
    meta = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for _, raw in zip(range(50), f):
                line = raw.strip()
                if line.startswith('* '):
                    break
                low = line.lower()
                if low.startswith('#+title:'):
                    meta['title'] = line.split(':', 1)[1].strip()
                elif low.startswith('#+author:'):
                    meta['author'] = line.split(':', 1)[1].strip()
    except Exception:
        return None
    return meta if 'title' in meta else None


def slug_to_display(slug: str) -> str:
    """john-chrysostom => John Chrysostom."""
    return slug.replace('-', ' ').title()


def generate_index(root: Path, lang: str, quiet: bool = False) -> Optional[Path]:
    """Generate index.org for one language directory."""
    lang_dir = root / 'content' / lang
    if not lang_dir.exists():
        return None

    manifests = load_manifests(root)
    greek_names = load_pg_greek_names(root)

    org_files = sorted(
        f for f in lang_dir.glob('*.org')
        if f.name != 'index.org' and not f.name.startswith(('.', '#'))
    )
    if not org_files:
        return None

    # Group by era => slug => works
    groups: Dict[str, Dict[str, List[Tuple[Path, str, str]]]] = {}
    uncategorized: List[Tuple[Path, str, str]] = []

    for fp in org_files:
        header = parse_header(fp)
        if not header:
            continue
        title = header['title']
        rel = f'content/{lang}/{fp.name}'
        source = manifests.get(rel, '')

        slug, _ = author_data.resolve_slug(fp)
        if slug:
            info = author_data.get_author(slug)
            if info:
                era = info['era']
                groups.setdefault(era, {}).setdefault(slug, []).append(
                    (fp, title, source)
                )
                continue
        uncategorized.append((fp, title, source))

    # Build output
    total = len(org_files)
    lang_title = LANG_TITLES.get(lang, lang)
    lines = [f'#+TITLE: {lang_title} ({total})', '']

    for era in ERA_ORDER:
        if era not in groups:
            continue
        slugs = groups[era]
        count = sum(len(v) for v in slugs.values())
        label = ERA_LABELS[era]

        lines.append(f'* {label} ({count}) :{era}:')

        for slug in sorted(slugs, key=lambda s: slug_to_display(s).lower()):
            works = slugs[slug]
            name_en = slug_to_display(slug)
            name_gr = greek_names.get(slug, '')
            heading = f'{name_gr} ({name_en})' if name_gr else name_en

            info = author_data.get_author(slug)
            century = info.get('century', '') if info else ''
            ctag = ' :' + century.replace('-', '_') + ':' if century else ''

            lines.append(f'** {heading}{ctag}')

            for fp, title, source in sorted(works, key=lambda w: w[1].lower()):
                stag = f' :{source}:' if source else ''
                lines.append(f'- [[file:{fp.name}][{title}]]{stag}')

        lines.append('')

    if uncategorized:
        lines.append(f'* Uncategorized ({len(uncategorized)})')
        for fp, title, source in sorted(uncategorized, key=lambda w: w[1].lower()):
            stag = f' :{source}:' if source else ''
            lines.append(f'- [[file:{fp.name}][{title}]]{stag}')
        lines.append('')

    out = lang_dir / 'index.org'
    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    if not quiet:
        print(f'Generated {out} ({total} files)')
    return out


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--quiet', action='store_true', help='Suppress output')
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    for lang in ['gr', 'en', 'la']:
        generate_index(root, lang, quiet=args.quiet)


if __name__ == '__main__':
    main()
