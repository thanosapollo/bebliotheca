#!/usr/bin/env python3
"""
Generate catalog JSON from Org-mode content files.

Scans content/en/ and content/gr/ directories for .org files,
extracts metadata from headers, and groups translations together.
"""

import os
import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


def parse_org_header(file_path: Path) -> Optional[Dict[str, str]]:
    """
    Parse Org-mode file header and extract metadata.

    Args:
        file_path: Path to the .org file

    Returns:
        Dictionary with metadata or None if parsing fails
    """
    metadata = {
        'filename': file_path.stem,
        'source_file': str(file_path)
    }

    # Determine language from directory structure
    if '/en/' in str(file_path):
        metadata['language'] = 'en'
        metadata['language_name'] = 'English'
    elif '/gr/' in str(file_path):
        metadata['language'] = 'gr'
        metadata['language_name'] = 'Greek'
    elif '/la/' in str(file_path):
        metadata['language'] = 'la'
        metadata['language_name'] = 'Latin'
    else:
        metadata['language'] = 'unknown'
        metadata['language_name'] = 'Unknown'

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # Read first 50 lines (headers are at the top)
            lines = [f.readline() for _ in range(50)]

            for line in lines:
                line = line.strip()

                # Stop at first content heading
                if line.startswith('* ') and not line.startswith('*'):
                    break

                # Extract TITLE
                if line.startswith('#+TITLE:') or line.startswith('#+title:'):
                    title = line.split(':', 1)[1].strip()
                    metadata['title'] = title

                # Extract AUTHOR
                elif line.startswith('#+AUTHOR:') or line.startswith('#+author:'):
                    author = line.split(':', 1)[1].strip()
                    metadata['author'] = author

                # Extract LANGUAGE (override directory-based detection)
                elif line.startswith('#+LANGUAGE:') or line.startswith('#+language:'):
                    lang = line.split(':', 1)[1].strip()
                    metadata['language'] = lang
                    if lang == 'el':
                        metadata['language_name'] = 'Greek'
                    elif lang == 'en':
                        metadata['language_name'] = 'English'
                    elif lang == 'la':
                        metadata['language_name'] = 'Latin'

                # Extract EXPORT_FILE_NAME (to determine HTML path)
                elif line.startswith('#+EXPORT_FILE_NAME:') or line.startswith('#+export_file_name:'):
                    export_path = line.split(':', 1)[1].strip()
                    # Convert relative path to web path
                    # ../../public/gr/iliad -> gr/iliad.html
                    export_path = export_path.replace('../../public/', '')
                    if not export_path.endswith('.html'):
                        export_path += '.html'
                    metadata['html_path'] = export_path

                # Extract DATE if present
                elif line.startswith('#+DATE:') or line.startswith('#+date:'):
                    date = line.split(':', 1)[1].strip()
                    metadata['date'] = date

                # Extract FILETAGS
                elif line.startswith('#+filetags:') or line.startswith('#+FILETAGS:'):
                    tags_line = line.split(':', 1)[1].strip()
                    # Split by colons and filter out empty strings
                    # Handles both :byzantine:roman: and :byzantine: :roman:
                    tags = [tag.strip() for tag in tags_line.split(':') if tag.strip()]
                    if tags:
                        metadata['tags'] = tags

        # Validate that we have minimum required fields
        if 'title' not in metadata:
            print(f"Warning: No title found in {file_path}")
            return None

        return metadata

    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return None


def scan_content_directory(base_path: Path) -> Dict[str, List[Dict[str, str]]]:
    """
    Scan content directory for .org files and group by filename.

    Args:
        base_path: Base path to the content directory

    Returns:
        Dictionary mapping filename to list of language versions
    """
    works_by_filename = {}

    # Scan en/, gr/, and la/ subdirectories
    for lang_dir in ['en', 'gr', 'la']:
        lang_path = base_path / lang_dir

        if not lang_path.exists():
            continue

        # Find all .org files (excluding index.org and temporary files)
        for org_file in lang_path.glob('*.org'):
            # Skip backup files and temp files
            if org_file.name.startswith('.') or org_file.name.startswith('#'):
                continue
            if org_file.name == 'index.org':
                continue

            print(f"Processing: {org_file}")
            metadata = parse_org_header(org_file)

            if metadata:
                filename = metadata['filename']

                # Group by filename
                if filename not in works_by_filename:
                    works_by_filename[filename] = []

                works_by_filename[filename].append(metadata)

    return works_by_filename


def group_translations(works_by_filename: Dict[str, List[Dict[str, str]]]) -> List[Dict]:
    """
    Convert grouped works into catalog format.

    Args:
        works_by_filename: Dictionary mapping filenames to translations

    Returns:
        List of work entries with grouped translations
    """
    catalog = []

    for filename, translations in works_by_filename.items():
        # Prefer Greek version for title/author, fallback to first available
        greek_version = next((t for t in translations if t['language'] in ('gr', 'el')), None)
        primary_version = greek_version or translations[0]

        # Create work entry
        work = {
            'id': filename,
            'title': primary_version.get('title', 'Untitled'),
            'author': primary_version.get('author', 'Unknown'),
            'translations': []
        }

        # Collect all unique tags from all translations
        all_tags = set()
        for trans in translations:
            if 'tags' in trans:
                all_tags.update(trans['tags'])

        if all_tags:
            work['tags'] = sorted(list(all_tags))

        # Add all translations
        for trans in translations:
            lang_code = trans['language']
            # Normalize language codes
            if lang_code == 'el':
                lang_code = 'gr'

            translation_entry = {
                'language': lang_code,
                'language_name': trans['language_name'],
                'html_path': trans.get('html_path', ''),
                'title': trans.get('title', ''),
                'author': trans.get('author', '')
            }

            # Add tags if present in this translation
            if 'tags' in trans:
                translation_entry['tags'] = trans['tags']

            work['translations'].append(translation_entry)

        # Sort translations by language priority: Greek, Latin, English
        lang_priority = {'gr': 0, 'la': 1, 'en': 2}
        work['translations'].sort(key=lambda t: lang_priority.get(t['language'], 99))

        catalog.append(work)

    return catalog


def generate_catalog_json(output_path: Path):
    """
    Generate catalog JSON file from content directory.

    Args:
        output_path: Path where the JSON file should be written
    """
    content_path = Path('content')

    if not content_path.exists():
        print(f"Error: Content directory not found: {content_path}")
        return

    print("Scanning content directory...")
    works_by_filename = scan_content_directory(content_path)

    print(f"\nGrouping translations...")
    catalog = group_translations(works_by_filename)

    # Sort by title (case-insensitive)
    catalog.sort(key=lambda x: x.get('title', '').lower())

    # Calculate statistics
    total_translations = sum(len(work['translations']) for work in catalog)
    greek_count = sum(1 for work in catalog for t in work['translations'] if t['language'] == 'gr')
    english_count = sum(1 for work in catalog for t in work['translations'] if t['language'] == 'en')
    latin_count = sum(1 for work in catalog for t in work['translations'] if t['language'] == 'la')

    # Create output structure
    output_data = {
        'generated_at': datetime.now().isoformat(),
        'total_works': len(catalog),
        'total_translations': total_translations,
        'statistics': {
            'unique_works': len(catalog),
            'translations': {
                'greek': greek_count,
                'english': english_count,
                'latin': latin_count
            }
        },
        'works': catalog
    }

    # Write JSON file
    print(f"\nWriting catalog to {output_path}...")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Generated catalog")
    print(f"  Unique works: {len(catalog)}")
    print(f"  Total translations: {total_translations}")
    print(f"    Greek: {greek_count}")
    print(f"    English: {english_count}")
    print(f"    Latin: {latin_count}")


if __name__ == '__main__':
    output_file = Path('public/catalog.json')
    generate_catalog_json(output_file)
