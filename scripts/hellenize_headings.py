#!/usr/bin/env python3
"""Replace English structural labels with Greek in content/gr/ heading lines.

Usage:
    python3 scripts/hellenize_headings.py              # Apply changes
    python3 scripts/hellenize_headings.py --dry-run    # Preview only
"""

import argparse
import glob
import re
import sys

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


def hellenize_file(path, dry_run=False):
    """Process one .org file. Returns (replacements, changed_lines) count."""
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    new_lines = []
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
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without modifying files')
    args = parser.parse_args()

    content_dir = 'content/gr'
    files = sorted(glob.glob(f'{content_dir}/*.org'))
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
