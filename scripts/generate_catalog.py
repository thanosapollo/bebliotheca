#!/usr/bin/env python3
"""Generate catalog JSON from Org-mode content files.

Scans content/{gr,en,la}/ directories for .org files, extracts metadata
from headers, groups translations by filename stem, and writes
public/catalog.json.

Usage:
    python3 scripts/generate_catalog.py                    # Default output
    python3 scripts/generate_catalog.py -o path/out.json   # Custom output
    python3 scripts/generate_catalog.py --quiet             # Suppress per-file output
"""

import argparse
import html
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from author_data import get_author, resolve_slug

# Language directory => display name
LANG_NAMES: Dict[str, str] = {
    'en': 'English',
    'gr': 'Greek',
    'el': 'Greek',
    'la': 'Latin',
}

# Translation sort priority: Greek first, then Latin, then English
LANG_PRIORITY: Dict[str, int] = {'gr': 0, 'la': 1, 'en': 2}
STATIC_CATALOG_LIMIT = 250
# Keep in lockstep with public/index.html and public/404.html cache-bust.
INDEX_CSS_CACHE_BUST = '21'


def normalize_display_label(label: str) -> str:
    """Remove importer suffixes from titles shown by catalog/readers."""
    label = re.sub(r'\bLiber (\d+)s\b', r'Liber \1', label)
    return re.sub(r'\b(\d+)s\b', r'Book \1', label)


def parse_org_header(file_path: Path) -> Optional[Dict[str, Any]]:
    """Parse Org-mode file header and extract metadata.

    Reads lines until the first heading (`* ...`) or 50 lines, whichever
    comes first. Returns a metadata dict, or None if no TITLE is found.
    """
    metadata: Dict[str, Any] = {
        'filename': file_path.stem,
        'source_file': str(file_path),
    }

    # Determine language from directory name
    lang_dir = file_path.parent.name
    metadata['language'] = lang_dir
    metadata['language_name'] = LANG_NAMES.get(lang_dir, 'Unknown')

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for _, raw_line in zip(range(50), f):
                line = raw_line.strip()

                # Stop at first Org heading
                if line.startswith('* '):
                    break

                low = line.lower()

                if low.startswith('#+title:'):
                    metadata['title'] = line.split(':', 1)[1].strip()

                elif low.startswith('#+author:'):
                    metadata['author'] = line.split(':', 1)[1].strip()

                elif low.startswith('#+language:'):
                    lang = line.split(':', 1)[1].strip()
                    metadata['language'] = lang
                    metadata['language_name'] = LANG_NAMES.get(lang, lang)

                elif low.startswith('#+export_file_name:'):
                    export_path = line.split(':', 1)[1].strip()
                    export_path = export_path.replace('../../public/', '')
                    if not export_path.endswith('.html'):
                        export_path += '.html'
                    metadata['html_path'] = export_path

                elif low.startswith('#+filetags:'):
                    tags_line = line.split(':', 1)[1].strip()
                    tags = [t.strip() for t in tags_line.split(':') if t.strip()]
                    if tags:
                        metadata['tags'] = tags

        if 'title' not in metadata:
            print(f"Warning: No title found in {file_path}")
            return None

        return metadata

    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None


def scan_content_directory(
    base_path: Path,
    quiet: bool = False,
) -> Dict[str, List[Dict[str, Any]]]:
    """Scan content directory for .org files and group by filename stem."""
    works: Dict[str, List[Dict[str, Any]]] = {}

    for lang_dir in ['en', 'gr', 'la']:
        lang_path = base_path / lang_dir
        if not lang_path.exists():
            continue

        for org_file in sorted(lang_path.glob('*.org')):
            if org_file.name.startswith(('.', '#')) or org_file.name == 'index.org':
                continue

            if not quiet:
                print(f"Processing: {org_file}")

            metadata = parse_org_header(org_file)
            if metadata:
                works.setdefault(metadata['filename'], []).append(metadata)

    return works


def group_translations(
    works_by_filename: Dict[str, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Convert grouped works into catalog format."""
    catalog: List[Dict[str, Any]] = []

    for filename, translations in works_by_filename.items():
        # Prefer Greek version for title/author
        greek = next((t for t in translations if t['language'] in ('gr', 'el')), None)
        primary = greek or translations[0]

        # Extract author slug from imported filenames (title--author-slug)
        author_latin = ''
        if '--' in filename:
            slug = filename.rsplit('--', 1)[1]
            # Convert slug to readable name: john-chrysostom => John Chrysostom
            author_latin = slug.replace('-', ' ').title()

        work: Dict[str, Any] = {
            'id': filename,
            'title': normalize_display_label(primary.get('title', 'Untitled')),
            'author': primary.get('author', 'Unknown'),
            'translations': [],
        }
        if author_latin:
            work['author_latin'] = author_latin
        author_id, _ = resolve_slug(Path(filename + '.org'))
        if author_id and get_author(author_id) is not None:
            work['author_id'] = author_id

        # Collect all unique tags across translations
        all_tags = {
            tag
            for trans in translations
            for tag in trans.get('tags', [])
        }
        if all_tags:
            work['tags'] = sorted(all_tags)

        # Build translation entries
        for trans in translations:
            lang_code = trans['language']
            if lang_code == 'el':
                lang_code = 'gr'

            entry: Dict[str, Any] = {
                'language': lang_code,
                'language_name': trans['language_name'],
                'html_path': trans.get('html_path', ''),
                'title': normalize_display_label(trans.get('title', '')),
                'author': trans.get('author', ''),
            }
            if 'tags' in trans:
                entry['tags'] = trans['tags']

            work['translations'].append(entry)

        work['translations'].sort(key=lambda t: LANG_PRIORITY.get(t['language'], 99))
        catalog.append(work)

    # Share observed primary names only within verified canonical identities.
    # Translation authors may contain translator names or importer annotations.
    aliases: Dict[str, set[str]] = {}
    for work in catalog:
        if 'author_id' in work:
            aliases.setdefault(work['author_id'], set()).update(
                name for name in (work['author'], work.get('author_latin'))
                if name and name != 'Unknown'
            )
    for work in catalog:
        if 'author_id' in work:
            work['author_aliases'] = sorted(aliases[work['author_id']])
    return catalog


def generate_static_catalog(catalog: List[Dict[str, Any]], output_path: Path) -> None:
    """Write a bounded no-JavaScript catalog from grouped catalog data."""
    items: List[str] = []
    letter_nav: List[str] = []
    seen_letters: set[str] = set()
    for work in catalog[:STATIC_CATALOG_LIMIT]:
        translations = work.get('translations', [])
        preferred = next((t for t in translations if t['language'] == 'gr'), None)
        preferred = preferred or next((t for t in translations if t['language'] == 'la'), None)
        preferred = preferred or (translations[0] if translations else None)
        if not preferred or not preferred.get('html_path'):
            continue
        title_raw = preferred.get('title') or work.get('title') or 'Untitled'
        title = html.escape(title_raw)
        author = html.escape(work.get('author') or 'Unknown')
        href = html.escape(preferred['html_path'], quote=True)
        letter = title_raw[:1].upper() if title_raw else '#'
        if letter not in seen_letters:
            seen_letters.add(letter)
            anchor = html.escape(letter, quote=True)
            letter_nav.append(f'<a href="#letter-{anchor}">{html.escape(letter)}</a>')
            items.append(
                f'<li class="static-letter" id="letter-{anchor}"><span>{html.escape(letter)}</span></li>'
            )
        items.append(
            f'<li><a href="{href}">{title}</a> <span class="static-author">{author}</span></li>'
        )

    nav = (
        f'<nav class="static-letter-nav" aria-label="Jump by title letter">'
        f'{"".join(letter_nav)}</nav>'
        if letter_nav
        else ''
    )
    document = f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bebliotheca static catalog</title><link rel="stylesheet" href="themes/src/index_theme/css/index.css?v={INDEX_CSS_CACHE_BUST}"></head>
<body><main class="container static-catalog-page"><h1>Bebliotheca catalog</h1>
<p class="static-catalog-meta">Showing {sum(1 for item in items if 'static-letter' not in item)} of {len(catalog)} works. <a href="index.html">Interactive catalog</a></p>
{nav}
<ol class="static-catalog">{''.join(items)}</ol></main></body></html>'''
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document, encoding='utf-8')


def generate_catalog(
    content_path: Path,
    output_path: Path,
    quiet: bool = False,
    static_output_path: Optional[Path] = None,
) -> None:
    """Generate catalog JSON file from content directory."""
    if not content_path.exists():
        print(f"Error: Content directory not found: {content_path}", file=sys.stderr)
        sys.exit(1)

    if not quiet:
        print("Scanning content directory...")
    works_by_filename = scan_content_directory(content_path, quiet=quiet)

    if not quiet:
        print("\nGrouping translations...")
    catalog = group_translations(works_by_filename)
    catalog.sort(key=lambda w: w.get('title', '').lower())

    # Statistics
    total_translations = sum(len(w['translations']) for w in catalog)
    greek_count = sum(1 for w in catalog for t in w['translations'] if t['language'] == 'gr')
    english_count = sum(1 for w in catalog for t in w['translations'] if t['language'] == 'en')
    latin_count = sum(1 for w in catalog for t in w['translations'] if t['language'] == 'la')

    output_data = {
        'generated_at': datetime.now().isoformat(),
        'total_works': len(catalog),
        'total_translations': total_translations,
        'statistics': {
            'unique_works': len(catalog),
            'translations': {
                'greek': greek_count,
                'english': english_count,
                'latin': latin_count,
            },
        },
        'works': catalog,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)
    if static_output_path is not None:
        generate_static_catalog(catalog, static_output_path)

    print(f"Generated catalog: {output_path}")
    print(f"  Unique works: {len(catalog)}")
    print(f"  Total translations: {total_translations}")
    print(f"    Greek: {greek_count}")
    print(f"    English: {english_count}")
    print(f"    Latin: {latin_count}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '-o', '--output',
        type=Path,
        default=Path('public/catalog.json'),
        help='Output path (default: public/catalog.json)',
    )
    parser.add_argument(
        '--static-output',
        type=Path,
        default=Path('public/catalog-static.html'),
        help='No-JavaScript catalog path (default: public/catalog-static.html)',
    )
    parser.add_argument(
        '--content-dir',
        type=Path,
        default=Path('content'),
        help='Content directory (default: content/)',
    )
    parser.add_argument(
        '--quiet', action='store_true',
        help='Suppress per-file processing output',
    )
    args = parser.parse_args()

    generate_catalog(
        args.content_dir,
        args.output,
        quiet=args.quiet,
        static_output_path=args.static_output,
    )


if __name__ == '__main__':
    main()
