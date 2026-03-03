#!/usr/bin/env python3
"""Convert Apostolic Fathers plain text files to Org-mode format.

Reads chapter.verse formatted Greek texts from sources/apostolic-fathers/texts/
and produces .org files in an output directory with proper headers and structure.

The source format is one verse per line:
    chapter.verse Greek text...

The Shepherd of Hermas uses three-level refs:
    section.chapter.verse Greek text...
where N.0.0 lines are section titles.

Usage:
    python3 scripts/convert_apostolic_to_org.py                    # Convert all
    python3 scripts/convert_apostolic_to_org.py --dry-run          # Preview only
    python3 scripts/convert_apostolic_to_org.py --output-dir DIR   # Custom output
"""

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ── Text metadata ──────────────────────────────────────────────────────
# Maps source filename to output metadata.
# stem: output filename stem (title--author-slug)
# title: Greek title for #+TITLE:
# author: Greek author name for #+AUTHOR:
# three_level: True for Shepherd of Hermas (section.chapter.verse format)
TEXTS: Dict[str, Dict[str, Any]] = {
    '001-i_clement.txt': {
        'stem': 'i-clement--clement-of-rome',
        'title': "Κλήμεντος πρὸς Κορινθίους Αʹ",
        'author': 'Κλήμης Ρώμης',
    },
    '002-ii_clement.txt': {
        'stem': 'ii-clement--clement-of-rome',
        'title': "Κλήμεντος πρὸς Κορινθίους Βʹ",
        'author': 'Κλήμης Ρώμης',
    },
    '003-ignatius-ephesians.txt': {
        'stem': 'pros-ephesious--ignatius-of-antioch',
        'title': "Ἰγνατίου πρὸς Ἐφεσίους",
        'author': 'Ἰγνάτιος Ἀντιοχείας',
    },
    '004-ignatius-magnesians.txt': {
        'stem': 'pros-magnesieis--ignatius-of-antioch',
        'title': "Ἰγνατίου πρὸς Μαγνησιεῖς",
        'author': 'Ἰγνάτιος Ἀντιοχείας',
    },
    '005-ignatius-trallians.txt': {
        'stem': 'pros-trallianous--ignatius-of-antioch',
        'title': "Ἰγνατίου πρὸς Τραλλιανούς",
        'author': 'Ἰγνάτιος Ἀντιοχείας',
    },
    '006-ignatius-romans.txt': {
        'stem': 'pros-romaious--ignatius-of-antioch',
        'title': "Ἰγνατίου πρὸς Ῥωμαίους",
        'author': 'Ἰγνάτιος Ἀντιοχείας',
    },
    '007-ignatius-philadelphians.txt': {
        'stem': 'pros-philadelpheis--ignatius-of-antioch',
        'title': "Ἰγνατίου πρὸς Φιλαδελφεῖς",
        'author': 'Ἰγνάτιος Ἀντιοχείας',
    },
    '008-ignatius-smyrnaeans.txt': {
        'stem': 'pros-smyrnaious--ignatius-of-antioch',
        'title': "Ἰγνατίου πρὸς Σμυρναίους",
        'author': 'Ἰγνάτιος Ἀντιοχείας',
    },
    '009-ignatius-polycarp.txt': {
        'stem': 'pros-polykarpon--ignatius-of-antioch',
        'title': "Ἰγνατίου πρὸς Πολύκαρπον",
        'author': 'Ἰγνάτιος Ἀντιοχείας',
    },
    '010-polycarp-philippians.txt': {
        'stem': 'pros-philippesious--polycarp-of-smyrna',
        'title': "Πολυκάρπου πρὸς Φιλιππησίους",
        'author': 'Πολύκαρπος Σμύρνης',
    },
    '011-didache.txt': {
        'stem': 'didache--twelve-apostles',
        'title': "Διδαχὴ τῶν Δώδεκα Ἀποστόλων",
        'author': 'Ἀνώνυμος',
    },
    # 012-barnabas.txt - SKIPPED (already in library from Perseus)
    '013-shepherd.txt': {
        'stem': 'poimen-tou-herma--hermas',
        'title': "Ποιμὴν τοῦ Ἑρμᾶ",
        'author': 'Ἑρμᾶς',
        'three_level': True,
    },
    '014-martyrdom.txt': {
        'stem': 'martyrion-polykarpos--church-of-smyrna',
        'title': "Μαρτύριον Πολυκάρπου",
        'author': 'Ἐκκλησία Σμύρνης',
    },
    '015-diognetus.txt': {
        'stem': 'pros-diogneton--mathetes',
        'title': "Πρὸς Διόγνητον",
        'author': 'Μαθητής',
    },
}

# Chapter 0 heading (epistolary preface / inscription)
CHAPTER_ZERO_HEADING = 'Ἐπιγραφή'


def parse_two_level(filepath: Path) -> Dict[int, List[Tuple[int, str]]]:
    """Parse chapter.verse formatted text into structured data.

    Returns dict: chapter_num => [(verse_num, text), ...]
    """
    chapters: Dict[int, List[Tuple[int, str]]] = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(\d+)\.(\d+)\s+(.+)$', line)
            if not match:
                continue
            ch = int(match.group(1))
            verse = int(match.group(2))
            text = match.group(3)
            chapters.setdefault(ch, []).append((verse, text))
    return chapters


def parse_three_level(filepath: Path) -> Dict[int, Dict[str, Any]]:
    """Parse section.chapter.verse formatted text (Shepherd of Hermas).

    Returns dict: section_num => {
        'title': str or None,
        'chapters': dict(chapter_num => [(verse_num, text), ...])
    }
    """
    sections: Dict[int, Dict[str, Any]] = {}
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            match = re.match(r'^(\d+)\.(\d+)\.(\d+)\s+(.+)$', line)
            if not match:
                continue
            sec = int(match.group(1))
            ch = int(match.group(2))
            verse = int(match.group(3))
            text = match.group(4)

            if sec not in sections:
                sections[sec] = {'title': None, 'chapters': {}}

            if ch == 0 and verse == 0:
                sections[sec]['title'] = text
            else:
                sections[sec]['chapters'].setdefault(ch, []).append((verse, text))
    return sections


def generate_org_two_level(meta: Dict[str, Any], chapters: Dict[int, List[Tuple[int, str]]]) -> str:
    """Generate Org-mode content for a two-level text."""
    lines: List[str] = [
        f'#+TITLE: {meta["title"]}',
        f'#+AUTHOR: {meta["author"]}',
        '#+SETUPFILE: ../../public/themes/org/theme-readtheorg-local.setup',
        '#+OPTIONS: ^:t num:nil html-style:nil date:nil html-postamble:nil',
        '#+startup: overview',
        f'#+EXPORT_FILE_NAME: ../../public/gr/{meta["stem"]}',
        '#+LANGUAGE: el',
        '',
    ]

    for ch_num, verses in chapters.items():
        heading = CHAPTER_ZERO_HEADING if ch_num == 0 else f'Κεφάλαιον {ch_num}'
        lines.extend([
            f'* {heading}',
            ':PROPERTIES:',
            f':CUSTOM_ID: ch-{ch_num}',
            ':END:',
            '',
        ])

        for verse_num, text in verses:
            lines.extend([
                f'** Τμῆμα {verse_num}',
                ':PROPERTIES:',
                f':CUSTOM_ID: ch-{ch_num}-sec-{verse_num}',
                ':END:',
                text,
                '',
            ])

    return '\n'.join(lines)


def generate_org_three_level(meta: Dict[str, Any], sections: Dict[int, Dict[str, Any]]) -> str:
    """Generate Org-mode content for the Shepherd of Hermas (three-level)."""
    lines: List[str] = [
        f'#+TITLE: {meta["title"]}',
        f'#+AUTHOR: {meta["author"]}',
        '#+SETUPFILE: ../../public/themes/org/theme-readtheorg-local.setup',
        '#+OPTIONS: ^:t num:nil html-style:nil date:nil html-postamble:nil',
        '#+startup: overview',
        f'#+EXPORT_FILE_NAME: ../../public/gr/{meta["stem"]}',
        '#+LANGUAGE: el',
        '',
    ]

    for sec_num, sec_data in sections.items():
        title = sec_data['title'] or f'Τμῆμα {sec_num}'
        lines.extend([
            f'* {title}',
            ':PROPERTIES:',
            f':CUSTOM_ID: sec-{sec_num}',
            ':END:',
            '',
        ])

        for ch_num, verses in sec_data['chapters'].items():
            lines.extend([
                f'** Κεφάλαιον {ch_num}',
                ':PROPERTIES:',
                f':CUSTOM_ID: sec-{sec_num}-ch-{ch_num}',
                ':END:',
                '',
            ])

            for verse_num, text in verses:
                lines.extend([
                    f'*** Τμῆμα {verse_num}',
                    ':PROPERTIES:',
                    f':CUSTOM_ID: sec-{sec_num}-ch-{ch_num}-sec-{verse_num}',
                    ':END:',
                    text,
                    '',
                ])

    return '\n'.join(lines)


def convert_text(
    source_path: Path,
    meta: Dict[str, Any],
    output_dir: Path,
    dry_run: bool = False,
) -> Optional[Path]:
    """Convert a single text file to Org-mode format.

    Returns output path on success, None on skip/error.
    """
    if meta.get('three_level'):
        data = parse_three_level(source_path)
        content = generate_org_three_level(meta, data)
    else:
        data = parse_two_level(source_path)
        content = generate_org_two_level(meta, data)

    output_path = output_dir / (meta['stem'] + '.org')

    if dry_run:
        if meta.get('three_level'):
            n_sections = len(data)
            n_chapters = sum(len(s['chapters']) for s in data.values())
            n_verses = sum(
                len(v)
                for s in data.values()
                for v in s['chapters'].values()
            )
            print(f'  {meta["stem"]}.org: {n_sections} sections, '
                  f'{n_chapters} chapters, {n_verses} verses')
        else:
            n_chapters = len(data)
            n_verses = sum(len(v) for v in data.values())
            print(f'  {meta["stem"]}.org: {n_chapters} chapters, {n_verses} verses')
        return output_path

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding='utf-8')
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Preview conversion without writing files',
    )
    parser.add_argument(
        '--output-dir', type=Path, default=None,
        help='Output directory (default: sources/apostolic-fathers/gr/)',
    )
    parser.add_argument(
        '--source-dir', type=Path, default=None,
        help='Source texts directory (default: sources/apostolic-fathers/texts/)',
    )
    args = parser.parse_args()

    root_dir = Path(__file__).resolve().parent.parent

    source_dir: Path = args.source_dir or root_dir / 'sources' / 'apostolic-fathers' / 'texts'
    output_dir: Path = args.output_dir or root_dir / 'sources' / 'apostolic-fathers' / 'gr'

    if not source_dir.is_dir():
        print(f'Source directory not found: {source_dir}', file=sys.stderr)
        sys.exit(1)

    converted = 0
    skipped = 0

    for filename, meta in TEXTS.items():
        source_path = source_dir / filename
        if not source_path.is_file():
            print(f'  [skip] {filename}: not found', file=sys.stderr)
            skipped += 1
            continue

        result = convert_text(source_path, meta, output_dir, args.dry_run)
        if result:
            converted += 1

    mode = 'Would convert' if args.dry_run else 'Converted'
    print(f'{mode} {converted} texts ({skipped} skipped).')


if __name__ == '__main__':
    main()
