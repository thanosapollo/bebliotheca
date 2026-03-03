#!/usr/bin/env python3
"""Replace English structural labels with Greek in content/gr/ heading lines.

Usage:
    python3 scripts/hellenize_headings.py              # Apply changes
    python3 scripts/hellenize_headings.py --dry-run    # Preview only
"""

import argparse
import re
import sys
from pathlib import Path
from typing import List

LABEL_MAP = {
    'Book': 'Βιβλίον',
    'Chapter': 'Κεφάλαιον',
    'Section': 'Τμῆμα',
    'Subsection': 'Ὑποτμῆμα',
    'Subchapter': 'Ὑποκεφάλαιον',
}

HEADING_RE = re.compile(
    r'^(\*+\s+)(Book|Chapter|Section|Subsection|Subchapter)(\s+.*)$'
)


def hellenize_file(path: Path, dry_run: bool = False) -> int:
    """Process one .org file. Returns number of headings replaced."""
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)

    new_lines: List[str] = []
    count = 0
    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            stars, label, rest = m.groups()
            new_lines.append(f"{stars}{LABEL_MAP[label]}{rest}\n")
            count += 1
        else:
            new_lines.append(line)

    if count > 0 and not dry_run:
        path.write_text(''.join(new_lines), encoding='utf-8')

    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without modifying files')
    args = parser.parse_args()

    content_dir = Path('content/gr')
    files = sorted(content_dir.glob('*.org'))
    if not files:
        print(f'No .org files found in {content_dir}/', file=sys.stderr)
        sys.exit(1)

    total_replacements = 0
    files_changed = 0

    for path in files:
        count = hellenize_file(path, dry_run=args.dry_run)
        if count > 0:
            files_changed += 1
            total_replacements += count
            if args.dry_run:
                print(f'  {path}: {count} headings')

    mode = 'Would replace' if args.dry_run else 'Replaced'
    print(f'{mode} {total_replacements} headings across {files_changed} files.')


if __name__ == '__main__':
    main()
