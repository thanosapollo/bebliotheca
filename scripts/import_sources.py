#!/usr/bin/env python3
"""Unified import pipeline for all Bebliotheca text sources.

Each source is a git submodule with a converter that produces .org files.
This script handles the full pipeline: init submodule, convert, copy to
content/, post-process (hellenize, tag), generate manifest, and clean up.

Usage:
    python3 scripts/import_sources.py                  # Import all (additive)
    python3 scripts/import_sources.py perseus-greek    # Import one source
    python3 scripts/import_sources.py --update         # Update submodules first
    python3 scripts/import_sources.py --list           # List available sources
    python3 scripts/import_sources.py --no-test        # Skip validation
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Set

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPTS_DIR.parent


def load_known_duplicates() -> Set[str]:
    """Load import filenames that are known duplicates of curated files."""
    dupes_file = ROOT_DIR / 'log' / 'known-duplicates.txt'
    names: Set[str] = set()
    if not dupes_file.exists():
        return names
    for line in dupes_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=>' in line:
            import_name = line.split('=>')[0].strip()
            names.add(import_name)
    return names

# ── Source definitions ─────────────────────────────────────────────────
# Each source describes a submodule and how to import it.
#
# Fields:
#   submodule      - path relative to project root
#   converter      - command to run (list of args); omit if source has no converter
#   converter_cwd  - 'submodule' or 'root' (where to run the converter)
#   output_langs   - language dirs the source provides (gr, en, la)
#   exclude        - glob patterns to remove after copy (matched against basename)
#   hellenize      - whether to run hellenize_headings.py after copy
#   manifest       - manifest file path relative to project root
#
# Sources without a 'converter' key skip submodule init, conversion,
# and converter cleanup. They just copy pre-existing .org files.

SOURCES: Dict[str, Dict[str, Any]] = {
    'perseus-greek': {
        'submodule': 'sources/canonical-greekLit',
        'converter': ['python3', str(SCRIPTS_DIR / 'convert_perseus_xml_to_org.py')],
        'converter_cwd': 'submodule',
        'output_langs': ['gr', 'en'],
        'exclude': ['*testament*'],
        'hellenize': True,
        'manifest': 'log/perseus-manifest.txt',
    },
    'perseus-latin': {
        'submodule': 'sources/canonical-latinLit',
        'converter': ['python3', str(SCRIPTS_DIR / 'convert_perseus_xml_to_org.py')],
        'converter_cwd': 'submodule',
        'output_langs': ['la', 'en', 'gr'],
        'exclude': [],
        'hellenize': False,
        'manifest': 'log/latinlit-manifest.txt',
    },
    'apostolic-fathers': {
        'submodule': 'sources/apostolic-fathers',
        'converter': ['python3', str(SCRIPTS_DIR / 'convert_apostolic_to_org.py')],
        'converter_cwd': 'root',
        'output_langs': ['gr'],
        'exclude': [],
        'hellenize': False,
        'manifest': 'log/apostolic-manifest.txt',
    },
    'pg-migne': {
        'submodule': 'sources/pg-migne',
        'output_langs': ['gr'],
        'exclude': [],
        'hellenize': False,
        'manifest': 'log/pg-migne-manifest.txt',
    },
}


def log(msg: str, indent: int = 0) -> None:
    """Print a status message with optional indentation, flushing immediately."""
    prefix = '  ' * indent
    print(f'{prefix}{msg}', flush=True)


def run(cmd: List[str], cwd: Path = None, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command, printing it first."""
    log(f'$ {" ".join(cmd)}', indent=2)
    return subprocess.run(cmd, cwd=cwd, check=check)


def init_submodule(source: Dict[str, Any]) -> None:
    """Ensure the git submodule is initialized."""
    log('Initializing submodule', indent=1)
    run(['git', '-C', str(ROOT_DIR), 'submodule', 'update', '--init',
         source['submodule']])


def update_submodule(source: Dict[str, Any]) -> None:
    """Update submodule to latest upstream."""
    submodule_path = ROOT_DIR / source['submodule']
    log('Updating to latest upstream', indent=1)
    run(['git', '-C', str(submodule_path), 'fetch', 'origin'])
    run(['git', '-C', str(submodule_path), 'checkout', 'origin/master'])
    result = subprocess.run(
        ['git', '-C', str(submodule_path), 'log', '--oneline', '-1'],
        capture_output=True, text=True)
    log(f'Now at: {result.stdout.strip()}', indent=2)


def clean_converter_output(source: Dict[str, Any]) -> None:
    """Remove previous converter output directories from submodule."""
    submodule_path = ROOT_DIR / source['submodule']
    for lang in source['output_langs']:
        lang_dir = submodule_path / lang
        if lang_dir.is_dir():
            shutil.rmtree(lang_dir)


def run_converter(source: Dict[str, Any]) -> None:
    """Run the source's converter script."""
    log('Running converter', indent=1)
    submodule_path = ROOT_DIR / source['submodule']
    cwd = submodule_path if source['converter_cwd'] == 'submodule' else ROOT_DIR
    run(source['converter'], cwd=cwd)


def has_auto_update_nil(path: Path) -> bool:
    """Check if a file has #+AUTO_UPDATE: nil in its header."""
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                if not line.startswith('#'):
                    break
                if line.strip().upper().startswith('#+AUTO_UPDATE:'):
                    return 'nil' in line.lower()
    except OSError:
        pass
    return False


def copy_to_content(source: Dict[str, Any]) -> List[str]:
    """Copy converter output to content/ directories.

    Overwrites existing files unless they have #+AUTO_UPDATE: nil.
    Returns list of skipped paths (relative to project root) for logging.
    """
    log('Copying to content/', indent=1)
    submodule_path = ROOT_DIR / source['submodule']
    content_dir = ROOT_DIR / 'content'
    known_dupes = load_known_duplicates()
    copied = 0
    updated = 0
    skipped: List[str] = []
    dup_skipped = 0
    for lang in source['output_langs']:
        src_dir = submodule_path / lang
        if not src_dir.is_dir():
            continue
        dst_dir = content_dir / lang
        dst_dir.mkdir(parents=True, exist_ok=True)
        for f in sorted(src_dir.glob('*.org')):
            if f.name in known_dupes:
                dup_skipped += 1
                continue
            dst = dst_dir / f.name
            if dst.exists():
                if has_auto_update_nil(dst):
                    skipped.append(f'content/{lang}/{f.name}')
                    continue
                shutil.copy2(f, dst_dir)
                updated += 1
            else:
                shutil.copy2(f, dst_dir)
                copied += 1
    msg = f'Copied {copied} new, updated {updated}, skipped {len(skipped)} (auto_update: nil)'
    if dup_skipped:
        msg += f', {dup_skipped} known duplicates'
    log(msg, indent=2)
    return skipped


def remove_excluded(source: Dict[str, Any]) -> None:
    """Remove files matching exclude patterns from content/ and converter output."""
    if not source['exclude']:
        return
    log('Removing excluded files', indent=1)
    submodule_path = ROOT_DIR / source['submodule']
    content_dir = ROOT_DIR / 'content'
    count = 0
    for pattern in source['exclude']:
        for lang in source['output_langs']:
            for f in (content_dir / lang).glob(pattern + '.org'):
                f.unlink()
                count += 1
            for f in (submodule_path / lang).glob(pattern + '.org'):
                f.unlink()
    log(f'Excluded {count} files', indent=2)


def hellenize_headings() -> None:
    """Run hellenize_headings.py to convert English labels to Greek."""
    log('Hellenizing Greek headings', indent=1)
    run(['python3', str(SCRIPTS_DIR / 'hellenize_headings.py')], cwd=ROOT_DIR)


def tag_pg_filetags() -> None:
    """Run tag_filetags.py --pg-tags to add PG volume tags."""
    log('Adding PG volume tags', indent=1)
    run(['python3', str(SCRIPTS_DIR / 'tag_filetags.py'), '--pg-tags'], cwd=ROOT_DIR)


def generate_manifest(source: Dict[str, Any]) -> None:
    """Generate the manifest file listing all imported files."""
    log('Generating manifest', indent=1)
    submodule_path = ROOT_DIR / source['submodule']
    manifest_path = ROOT_DIR / source['manifest']
    manifest_path.parent.mkdir(exist_ok=True)
    entries: List[str] = []
    for lang in source['output_langs']:
        lang_dir = submodule_path / lang
        if not lang_dir.is_dir():
            continue
        for f in sorted(lang_dir.glob('*.org')):
            entries.append(f'content/{lang}/{f.name}')
    entries.sort()
    manifest_path.write_text('\n'.join(entries) + '\n' if entries else '')
    log(f'{len(entries)} files in manifest', indent=2)


def run_tests() -> None:
    """Run make test to validate imported content."""
    log('==> Running validation')
    run(['make', 'test'], cwd=ROOT_DIR)


def generate_reports() -> None:
    """Write detailed test reports to log/."""
    log_dir = ROOT_DIR / 'log'
    log_dir.mkdir(exist_ok=True)
    reports = [
        ('structure-report.txt', 'check_structure.py'),
        ('language-report.txt', 'check_language.py'),
        ('originals-report.txt', 'check_originals.py'),
        ('metadata-report.txt', 'check_metadata.py'),
    ]
    log('==> Writing reports to log/')
    for filename, script in reports:
        result = subprocess.run(
            [sys.executable, str(ROOT_DIR / 'tests' / script), 'report'],
            cwd=ROOT_DIR, capture_output=True, text=True,
        )
        (log_dir / filename).write_text(result.stdout)
        log(filename, indent=1)


def write_skipped_log(source: Dict[str, Any], skipped: List[str]) -> None:
    """Write skipped (already existing) files to a log file."""
    if not skipped:
        return
    log_dir = ROOT_DIR / 'log'
    log_dir.mkdir(exist_ok=True)
    # Derive log name from manifest name: perseus-manifest.txt => perseus-skipped.txt
    manifest_name = Path(source['manifest']).name
    skipped_name = manifest_name.replace('-manifest.txt', '-skipped.txt')
    skipped_path = log_dir / skipped_name
    skipped_path.write_text('\n'.join(skipped) + '\n')
    log(f'{len(skipped)} skipped files written to {skipped_path.relative_to(ROOT_DIR)}',
        indent=2)


def import_source(name: str, source: Dict[str, Any], update: bool = False) -> None:
    """Run the full import pipeline for a single source."""
    log(f'==> Importing {name}')
    has_converter = 'converter' in source
    if has_converter:
        init_submodule(source)
        if update:
            update_submodule(source)
        clean_converter_output(source)
        run_converter(source)
    skipped = copy_to_content(source)
    remove_excluded(source)
    if source['hellenize']:
        hellenize_headings()
    if name == 'pg-migne':
        tag_pg_filetags()
    generate_manifest(source)
    write_skipped_log(source, skipped)
    if has_converter:
        clean_converter_output(source)
    log(f'==> {name} import complete')
    if update and has_converter:
        log('Submodule updated. Remember to stage:', indent=1)
        log(f'git add {source["submodule"]}', indent=2)


def main() -> None:
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

    generate_reports()


if __name__ == '__main__':
    main()
