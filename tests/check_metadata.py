#!/usr/bin/env python3
"""
Validate metadata quality across all .org content files.

Checks for missing/empty required headers (TITLE, AUTHOR, EXPORT_FILE_NAME,
LANGUAGE), placeholder values on auto-generated files, and invalid FILETAG
values.

Errors cause CI failure; warnings are informational.
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Valid era tags (Constantinople's classification)
VALID_ERA_TAGS = {'classical', 'imperial', 'patristic', 'byzantine', 'scripture'}

# Century tags match this pattern
CENTURY_RE = re.compile(r'^\d+c-(bc|ad)$')

# PG volume tags: pg88, pg47-64, pg86a, etc.
PG_TAG_RE = re.compile(r'^pg\d+[a-z]?(-\d+[a-z]?)?$')

# Placeholder values that indicate incomplete imports
PLACEHOLDER_TITLES = {'untitled', ''}
PLACEHOLDER_AUTHORS = {'unknown', ''}


def is_auto_generated(stem: str) -> bool:
    """Check if a file is auto-generated (has double-dash in name)."""
    return '--' in stem


def parse_headers(file_path: Path) -> Dict[str, Optional[str]]:
    """Parse Org-mode headers from a file. Returns dict of header values."""
    headers: Dict[str, Optional[str]] = {
        'title': None,
        'author': None,
        'export_file_name': None,
        'language': None,
        'filetags': None,
    }

    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            # Stop at first heading
            if stripped.startswith('*'):
                break
            low = stripped.lower()
            if low.startswith('#+title:'):
                headers['title'] = stripped.split(':', 1)[1].strip()
            elif low.startswith('#+author:'):
                headers['author'] = stripped.split(':', 1)[1].strip()
            elif low.startswith('#+export_file_name:'):
                headers['export_file_name'] = stripped.split(':', 1)[1].strip()
            elif low.startswith('#+language:'):
                headers['language'] = stripped.split(':', 1)[1].strip()
            elif low.startswith('#+filetags:'):
                headers['filetags'] = stripped.split(':', 1)[1].strip()

    return headers


def parse_tags(filetags_value: str) -> List[str]:
    """Parse tag names from a FILETAGS value like ':classical:8c-bc:'."""
    return [t for t in filetags_value.split(':') if t]


def is_valid_tag(tag: str) -> bool:
    """Check if a tag is a valid era, century, or PG volume tag."""
    return (tag in VALID_ERA_TAGS
            or bool(CENTURY_RE.match(tag))
            or bool(PG_TAG_RE.match(tag)))


def check_file(file_path: Path, lang_dir: str) -> Tuple[List[str], List[str]]:
    """
    Validate metadata for a single .org file.

    Returns (errors, warnings) where each is a list of message strings.
    """
    errors = []
    warnings = []
    stem = file_path.stem
    auto = is_auto_generated(stem)
    rel = f'{lang_dir}/{file_path.name}'

    headers = parse_headers(file_path)

    # Required: TITLE
    if headers['title'] is None:
        errors.append(f'{rel}: missing #+TITLE:')
    elif auto and headers['title'].lower() in PLACEHOLDER_TITLES:
        warnings.append(f'{rel}: placeholder TITLE "{headers["title"]}"')

    # Required: AUTHOR
    if headers['author'] is None:
        errors.append(f'{rel}: missing #+AUTHOR:')
    elif auto and headers['author'].lower() in PLACEHOLDER_AUTHORS:
        warnings.append(f'{rel}: placeholder AUTHOR "{headers["author"]}"')

    # Required: EXPORT_FILE_NAME
    if headers['export_file_name'] is None:
        errors.append(f'{rel}: missing #+EXPORT_FILE_NAME:')

    # LANGUAGE (warning-only - directory placement is authoritative)
    if headers['language'] is None:
        warnings.append(f'{rel}: missing #+LANGUAGE:')

    # FILETAGS validation
    if headers['filetags'] is not None:
        tags = parse_tags(headers['filetags'])
        invalid = [t for t in tags if not is_valid_tag(t)]
        if invalid:
            errors.append(f'{rel}: invalid FILETAG(s): {", ".join(invalid)}')
    elif auto:
        warnings.append(f'{rel}: auto-generated file missing #+FILETAGS:')

    return errors, warnings


def scan_all(content_dir: Path) -> Tuple[List[str], List[str]]:
    """Scan all .org files and collect errors/warnings."""
    all_errors = []
    all_warnings = []

    for lang_dir in ['gr', 'en', 'la']:
        lang_path = content_dir / lang_dir
        if not lang_path.exists():
            continue

        for org_file in sorted(lang_path.glob('*.org')):
            if org_file.name.startswith('.') or org_file.name.startswith('#'):
                continue
            if org_file.name == 'index.org':
                continue

            errors, warnings = check_file(org_file, lang_dir)
            all_errors.extend(errors)
            all_warnings.extend(warnings)

    return all_errors, all_warnings


def main():
    parser = argparse.ArgumentParser(
        description='Validate metadata quality across all .org content files.'
    )
    parser.add_argument(
        'mode',
        choices=['check', 'report'],
        help='check: exit 0/1 for CI (errors only); report: detailed output',
    )
    parser.add_argument(
        '--content-dir',
        type=Path,
        default=None,
        help='Path to the content directory (default: auto-detect)',
    )

    args = parser.parse_args()

    from utils import resolve_content_dir
    content_dir = resolve_content_dir(args.content_dir)

    errors, warnings = scan_all(content_dir)

    if args.mode == 'report':
        print('=' * 60)
        print('  Metadata Quality Report')
        print('=' * 60)
        print()

        if errors:
            print(f'ERRORS ({len(errors)}):')
            print('-' * 60)
            for msg in errors:
                print(f'  [ERROR] {msg}')
            print()

        if warnings:
            print(f'WARNINGS ({len(warnings)}):')
            print('-' * 60)
            for msg in warnings:
                print(f'  [WARN]  {msg}')
            print()

        if not errors and not warnings:
            print('All files have valid metadata.')
            print()

        print(f'SUMMARY: {len(errors)} error(s), {len(warnings)} warning(s)')

    elif args.mode == 'check':
        if errors:
            for msg in errors:
                print(f'[ERROR] {msg}')
            print(f'\nFAIL: {len(errors)} metadata error(s)')
            if warnings:
                print(f'  ({len(warnings)} warning(s) not shown - use report mode)')
            sys.exit(1)
        else:
            msg = 'OK: All files have valid metadata.'
            if warnings:
                msg += f' ({len(warnings)} warning(s) - use report mode)'
            print(msg)
            sys.exit(0)


if __name__ == '__main__':
    main()
