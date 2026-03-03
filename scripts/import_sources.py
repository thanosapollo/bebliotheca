#!/usr/bin/env python3
"""Unified import pipeline for all Bebliotheca text sources.

Each source is a git submodule with a converter that produces .org files.
This script handles the full pipeline: init submodule, convert, copy to
content/, post-process (hellenize, tag), generate manifest, and clean up.

Usage:
    python3 scripts/import_sources.py                  # Import all sources
    python3 scripts/import_sources.py perseus-greek    # Import one source
    python3 scripts/import_sources.py --update         # Update submodules first
    python3 scripts/import_sources.py --list           # List available sources
    python3 scripts/import_sources.py --no-test        # Skip validation
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPTS_DIR)

# ── Source definitions ─────────────────────────────────────────────────
# Each source describes a submodule and how to import it.
#
# Fields:
#   submodule      - path relative to project root
#   converter      - command to run (list of args)
#   converter_cwd  - 'submodule' or 'root' (where to run the converter)
#   output_langs   - language dirs the converter produces (gr, en, la)
#   exclude        - glob patterns to remove after copy (matched against basename)
#   hellenize      - whether to run hellenize_headings.py after copy
#   manifest       - manifest file path relative to project root

SOURCES = {
    'perseus-greek': {
        'submodule': 'sources/canonical-greekLit',
        'converter': ['python3', os.path.join(SCRIPTS_DIR, 'convert_perseus_xml_to_org.py')],
        'converter_cwd': 'submodule',
        'output_langs': ['gr', 'en'],
        'exclude': ['*testament*'],
        'hellenize': True,
        'manifest': 'sources/perseus-manifest.txt',
    },
    'perseus-latin': {
        'submodule': 'sources/canonical-latinLit',
        'converter': ['python3', os.path.join(SCRIPTS_DIR, 'convert_perseus_xml_to_org.py')],
        'converter_cwd': 'submodule',
        'output_langs': ['la', 'en', 'gr'],
        'exclude': [],
        'hellenize': False,
        'manifest': 'sources/latinlit-manifest.txt',
    },
    'apostolic-fathers': {
        'submodule': 'sources/apostolic-fathers',
        'converter': ['python3', os.path.join(SCRIPTS_DIR, 'convert_apostolic_to_org.py')],
        'converter_cwd': 'root',
        'output_langs': ['gr'],
        'exclude': [],
        'hellenize': False,
        'manifest': 'sources/apostolic-manifest.txt',
    },
}


def log(msg, indent=0):
    """Print a status message with optional indentation, flushing immediately."""
    prefix = '  ' * indent
    print(f'{prefix}{msg}', flush=True)


def run(cmd, cwd=None, check=True):
    """Run a command, printing it first."""
    log(f'$ {" ".join(cmd)}', indent=2)
    return subprocess.run(cmd, cwd=cwd, check=check)


def init_submodule(source):
    """Ensure the git submodule is initialized."""
    log('Initializing submodule', indent=1)
    run(['git', '-C', ROOT_DIR, 'submodule', 'update', '--init',
         source['submodule']])


def update_submodule(source):
    """Update submodule to latest upstream."""
    submodule_path = os.path.join(ROOT_DIR, source['submodule'])
    log('Updating to latest upstream', indent=1)
    run(['git', '-C', submodule_path, 'fetch', 'origin'])
    run(['git', '-C', submodule_path, 'checkout', 'origin/master'])
    result = subprocess.run(
        ['git', '-C', submodule_path, 'log', '--oneline', '-1'],
        capture_output=True, text=True)
    log(f'Now at: {result.stdout.strip()}', indent=2)


def clean_converter_output(source):
    """Remove previous converter output directories from submodule."""
    submodule_path = os.path.join(ROOT_DIR, source['submodule'])
    for lang in source['output_langs']:
        lang_dir = os.path.join(submodule_path, lang)
        if os.path.isdir(lang_dir):
            shutil.rmtree(lang_dir)


def run_converter(source):
    """Run the source's converter script."""
    log('Running converter', indent=1)
    submodule_path = os.path.join(ROOT_DIR, source['submodule'])
    if source['converter_cwd'] == 'submodule':
        cwd = submodule_path
    else:
        cwd = ROOT_DIR
    run(source['converter'], cwd=cwd)


def remove_stale_files(source):
    """Remove files listed in the previous manifest."""
    manifest_path = os.path.join(ROOT_DIR, source['manifest'])
    if not os.path.isfile(manifest_path):
        return
    log('Removing stale files from previous manifest', indent=1)
    count = 0
    with open(manifest_path, 'r') as f:
        for line in f:
            filepath = os.path.join(ROOT_DIR, line.strip())
            if os.path.isfile(filepath):
                os.remove(filepath)
                count += 1
    log(f'Removed {count} files', indent=2)


def copy_to_content(source):
    """Copy converter output to content/ directories."""
    log('Copying to content/', indent=1)
    submodule_path = os.path.join(ROOT_DIR, source['submodule'])
    content_dir = os.path.join(ROOT_DIR, 'content')
    copied = 0
    for lang in source['output_langs']:
        src_dir = os.path.join(submodule_path, lang)
        if not os.path.isdir(src_dir):
            continue
        dst_dir = os.path.join(content_dir, lang)
        os.makedirs(dst_dir, exist_ok=True)
        for f in glob.glob(os.path.join(src_dir, '*.org')):
            shutil.copy2(f, dst_dir)
            copied += 1
    log(f'Copied {copied} files', indent=2)


def remove_excluded(source):
    """Remove files matching exclude patterns from content/ and converter output."""
    if not source['exclude']:
        return
    log('Removing excluded files', indent=1)
    submodule_path = os.path.join(ROOT_DIR, source['submodule'])
    content_dir = os.path.join(ROOT_DIR, 'content')
    count = 0
    for pattern in source['exclude']:
        for lang in source['output_langs']:
            for f in glob.glob(os.path.join(content_dir, lang, pattern + '.org')):
                os.remove(f)
                count += 1
            for f in glob.glob(os.path.join(submodule_path, lang, pattern + '.org')):
                os.remove(f)
    log(f'Excluded {count} files', indent=2)


def hellenize_headings():
    """Run hellenize_headings.py to convert English labels to Greek."""
    log('Hellenizing Greek headings', indent=1)
    run(['python3', os.path.join(SCRIPTS_DIR, 'hellenize_headings.py')],
        cwd=ROOT_DIR)


def tag_filetags():
    """Run tag_filetags.py to insert FILETAGS based on author classification."""
    log('Tagging files', indent=1)
    run(['python3', os.path.join(SCRIPTS_DIR, 'tag_filetags.py')],
        cwd=ROOT_DIR)


def generate_manifest(source):
    """Generate the manifest file listing all imported files."""
    log('Generating manifest', indent=1)
    submodule_path = os.path.join(ROOT_DIR, source['submodule'])
    manifest_path = os.path.join(ROOT_DIR, source['manifest'])
    entries = []
    for lang in source['output_langs']:
        lang_dir = os.path.join(submodule_path, lang)
        if not os.path.isdir(lang_dir):
            continue
        for f in sorted(glob.glob(os.path.join(lang_dir, '*.org'))):
            entries.append(f'content/{lang}/{os.path.basename(f)}')
    entries.sort()
    with open(manifest_path, 'w') as f:
        f.write('\n'.join(entries) + '\n' if entries else '')
    log(f'{len(entries)} files in manifest', indent=2)


def run_tests():
    """Run make test to validate imported content."""
    log('==> Running validation')
    run(['make', 'test'], cwd=ROOT_DIR)


def import_source(name, source, update=False):
    """Run the full import pipeline for a single source."""
    log(f'==> Importing {name}')
    init_submodule(source)
    if update:
        update_submodule(source)
    clean_converter_output(source)
    run_converter(source)
    remove_stale_files(source)
    copy_to_content(source)
    remove_excluded(source)
    if source['hellenize']:
        hellenize_headings()
    tag_filetags()
    generate_manifest(source)
    clean_converter_output(source)
    log(f'==> {name} import complete')
    if update:
        log(f'Submodule updated. Remember to stage:', indent=1)
        log(f'git add {source["submodule"]}', indent=2)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        'sources', nargs='*', default=[],
        help='Source names to import (default: all)',
    )
    parser.add_argument(
        '--update', action='store_true',
        help='Update submodules to latest upstream before importing',
    )
    parser.add_argument(
        '--list', action='store_true',
        help='List available sources and exit',
    )
    parser.add_argument(
        '--no-test', action='store_true',
        help='Skip running tests after import',
    )
    args = parser.parse_args()

    if args.list:
        for name, source in SOURCES.items():
            print(f'  {name:20s} {source["submodule"]}')
        return

    # Determine which sources to import
    if args.sources:
        for name in args.sources:
            if name not in SOURCES:
                print(f'Unknown source: {name}', file=sys.stderr)
                print(f'Available: {", ".join(SOURCES)}', file=sys.stderr)
                sys.exit(1)
        selected = {name: SOURCES[name] for name in args.sources}
    else:
        selected = SOURCES

    for name, source in selected.items():
        import_source(name, source, update=args.update)

    if not args.no_test:
        run_tests()


if __name__ == '__main__':
    main()
