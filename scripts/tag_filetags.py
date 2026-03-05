#!/usr/bin/env python3
"""Insert #+FILETAGS: in .org files based on author classification.

Scans content/{gr,en,la}/ for .org files, resolves the author slug from
the filename (title--author-slug.org) or stem_overrides (for manually
curated files), and inserts a #+FILETAGS: line with era + century tags.

Author data is loaded from scripts/authors.json via author_data.py.

Usage:
    python3 scripts/tag_filetags.py              # Tag untagged files
    python3 scripts/tag_filetags.py --dry-run    # Preview only
    python3 scripts/tag_filetags.py --pg-tags    # Add PG volume tags from manifest
"""

import argparse
import json
import re
import sys
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from author_data import build_filetags, get_author, load_authors, resolve_slug

# ── Century pattern ──────────────────────────────────────────────────
CENTURY_RE = re.compile(r'^\d+c-(bc|ad)$')


class Result(Enum):
    """Outcome of tagging a single file."""
    TAGGED = auto()
    SKIPPED_EXISTING = auto()
    SKIPPED_UNKNOWN = auto()
    SKIPPED_NO_SLUG = auto()


def parse_filetags(line: str) -> List[str]:
    """Parse tag names from a #+FILETAGS: line. Returns list of strings."""
    value = re.split(r'(?i)#\+filetags:\s*', line, maxsplit=1)
    if len(value) < 2:
        return []
    return [t for t in value[1].strip().split(':') if t]


def tag_file(
    path: Path,
    dry_run: bool = False,
) -> Tuple[Result, Optional[str]]:
    """Insert #+FILETAGS: based on author classification.

    Inserts FILETAGS (era + century) if none exists.
    Returns (Result, value_or_slug_or_None).
    """
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)

    slug, stem = resolve_slug(path)
    if slug is None:
        return Result.SKIPPED_NO_SLUG, None

    if get_author(slug) is None:
        return Result.SKIPPED_UNKNOWN, slug

    # Check for existing #+FILETAGS: line
    for line in lines:
        if line.startswith('#+FILETAGS:'):
            return Result.SKIPPED_EXISTING, None

    # No FILETAGS exists - insert after #+AUTHOR:
    filetags_value = build_filetags(slug)
    if filetags_value is None:
        return Result.SKIPPED_UNKNOWN, slug

    new_lines: List[str] = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if not inserted and line.lower().startswith('#+author:'):
            new_lines.append(f'#+FILETAGS: {filetags_value}\n')
            inserted = True

    if not inserted:
        new_lines.insert(1, f'#+FILETAGS: {filetags_value}\n')

    if not dry_run:
        path.write_text(''.join(new_lines), encoding='utf-8')

    return Result.TAGGED, filetags_value


# ── PG volume tagging ──────────────────────────────────────────────

PG_SPEC_RE = re.compile(r'_\s*PG\s*(.+?)/')


def parse_pg_spec(spec: str) -> List[str]:
    """Parse a PG volume spec into a list of tag strings.

    Examples:
        '88'          => ['pg88']
        '47-64'       => ['pg47-64']
        '86a'         => ['pg86a']
        '86B'         => ['pg86b']
        '87a-87c'     => ['pg87a', 'pg87b', 'pg87c']
        '34,65'       => ['pg34', 'pg65']
        '105,111,117' => ['pg105', 'pg111', 'pg117']
        ' 25-28'      => ['pg25-28']
    """
    spec = spec.strip().lower()
    tags: List[str] = []

    # Split on comma first (composite specs)
    parts = [p.strip() for p in spec.split(',')]
    for part in parts:
        if not part:
            continue
        # Check for letter-suffix range: e.g. 87a-87c
        m = re.match(r'^(\d+)([a-z])-\d+([a-z])$', part)
        if m:
            num, start_letter, end_letter = m.group(1), m.group(2), m.group(3)
            for c in range(ord(start_letter), ord(end_letter) + 1):
                tags.append(f'pg{num}{chr(c)}')
            continue
        # Plain spec (single number, range, or number+letter)
        tags.append(f'pg{part}')

    return tags


def add_pg_tag_to_file(
    path: Path,
    pg_tags: List[str],
    dry_run: bool = False,
) -> Tuple[str, Optional[str]]:
    """Add PG volume tags to existing FILETAGS line.

    Returns (status, detail) where status is 'tagged', 'skipped_has_pg',
    'skipped_no_filetags', or 'error'.
    """
    try:
        text = path.read_text(encoding='utf-8')
    except OSError as e:
        return 'error', str(e)

    lines = text.splitlines(keepends=True)

    filetags_idx: Optional[int] = None
    existing_tags: List[str] = []
    for i, line in enumerate(lines):
        if line.startswith('#+FILETAGS:'):
            filetags_idx = i
            existing_tags = parse_filetags(line)
            break

    if filetags_idx is None:
        return 'skipped_no_filetags', None

    # Skip if any pg tag already present
    if any(t.startswith('pg') for t in existing_tags):
        return 'skipped_has_pg', None

    new_tags = existing_tags + pg_tags
    new_value = ':' + ':'.join(new_tags) + ':'

    if not dry_run:
        lines[filetags_idx] = f'#+FILETAGS: {new_value}\n'
        path.write_text(''.join(lines), encoding='utf-8')

    return 'tagged', new_value


def run_pg_tags(dry_run: bool = False) -> None:
    """Add PG volume tags to all PG Migne files using the PDF manifest."""
    manifest_path = Path('log/pg-migne-pdf-manifest.json')
    if not manifest_path.exists():
        print(f'Manifest not found: {manifest_path}', file=sys.stderr)
        sys.exit(1)

    manifest: Dict[str, str] = json.loads(
        manifest_path.read_text(encoding='utf-8'))

    content_gr = Path('content/gr')
    tagged = 0
    skipped_has_pg = 0
    skipped_no_filetags = 0
    skipped_not_found = 0
    errors = 0

    for org_name, pdf_path in sorted(manifest.items()):
        org_path = content_gr / org_name
        if not org_path.exists():
            skipped_not_found += 1
            continue

        m = PG_SPEC_RE.search(pdf_path)
        if not m:
            errors += 1
            print(f'  [err] No PG spec in path: {pdf_path}', file=sys.stderr)
            continue

        pg_tags = parse_pg_spec(m.group(1))
        if not pg_tags:
            errors += 1
            print(f'  [err] Empty tags for spec: {m.group(1)}', file=sys.stderr)
            continue

        status, detail = add_pg_tag_to_file(org_path, pg_tags, dry_run=dry_run)

        if status == 'tagged':
            tagged += 1
            if dry_run:
                print(f'  [pg] {org_name}: {detail}')
        elif status == 'skipped_has_pg':
            skipped_has_pg += 1
        elif status == 'skipped_no_filetags':
            skipped_no_filetags += 1
        elif status == 'error':
            errors += 1
            print(f'  [err] {org_name}: {detail}', file=sys.stderr)

    mode = 'Would tag' if dry_run else 'Tagged'
    print(f'{mode} {tagged} files with PG volume tags; '
          f'skipped {skipped_has_pg} (already have pg tags), '
          f'{skipped_no_filetags} (no FILETAGS line), '
          f'{skipped_not_found} (file not found); '
          f'{errors} errors.')


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without modifying files')
    parser.add_argument('--pg-tags', action='store_true',
                        help='Add PG volume tags from pg-migne-pdf-manifest.json')
    args = parser.parse_args()

    if args.pg_tags:
        run_pg_tags(dry_run=args.dry_run)
        return

    content_dirs = [Path('content') / d for d in ('gr', 'en', 'la')]
    files = [
        f
        for d in content_dirs
        if d.exists()
        for f in sorted(d.glob('*.org'))
    ]

    if not files:
        print('No .org files found in content/{gr,en,la}/', file=sys.stderr)
        sys.exit(1)

    # Accumulate results
    counts: Dict[Result, int] = {r: 0 for r in Result}
    unknown_slugs: set = set()

    for path in files:
        result, value = tag_file(path, dry_run=args.dry_run)
        counts[result] += 1

        if result == Result.TAGGED and args.dry_run:
            print(f'  [new] {path}: {value}')
        elif result == Result.SKIPPED_UNKNOWN and value:
            unknown_slugs.add(value)

    # Summary
    mode = 'Would' if args.dry_run else 'Did'
    parts: List[str] = []
    if counts[Result.TAGGED]:
        parts.append(f'tag {counts[Result.TAGGED]}')
    if not parts:
        parts.append('change 0')

    skip_parts: List[str] = []
    if counts[Result.SKIPPED_EXISTING]:
        skip_parts.append(f'{counts[Result.SKIPPED_EXISTING]} already tagged')
    if counts[Result.SKIPPED_UNKNOWN]:
        skip_parts.append(f'{counts[Result.SKIPPED_UNKNOWN]} unknown author')
    if counts[Result.SKIPPED_NO_SLUG]:
        skip_parts.append(f'{counts[Result.SKIPPED_NO_SLUG]} no author slug')

    summary = f'{mode} {", ".join(parts)} files'
    if skip_parts:
        summary += f'; skipped {", ".join(skip_parts)}'
    print(summary + '.')

    if unknown_slugs:
        print(f'Unknown author slugs: {", ".join(sorted(unknown_slugs))}')


if __name__ == '__main__':
    main()
