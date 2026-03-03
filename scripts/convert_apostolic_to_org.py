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
import os
import re
import sys
from collections import OrderedDict

# ── Text metadata ──────────────────────────────────────────────────────
# Maps source filename to output metadata.
# stem: output filename stem (title--author-slug)
# title: Greek title for #+TITLE:
# author: Greek author name for #+AUTHOR:
# three_level: True for Shepherd of Hermas (section.chapter.verse format)
TEXTS = {
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


def parse_two_level(filepath):
    """Parse chapter.verse formatted text into structured data.

    Returns OrderedDict: chapter_num -> [(verse_num, text), ...]
    """
    chapters = OrderedDict()
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
            if ch not in chapters:
                chapters[ch] = []
            chapters[ch].append((verse, text))
    return chapters


def parse_three_level(filepath):
    """Parse section.chapter.verse formatted text (Shepherd of Hermas).

    Returns OrderedDict: section_num -> {
        'title': str or None,
        'chapters': OrderedDict(chapter_num -> [(verse_num, text), ...])
    }
    """
    sections = OrderedDict()
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
                sections[sec] = {'title': None, 'chapters': OrderedDict()}

            if ch == 0 and verse == 0:
                # Section title line (e.g., "Ὅρασις αʹ")
                sections[sec]['title'] = text
            else:
                if ch not in sections[sec]['chapters']:
                    sections[sec]['chapters'][ch] = []
                sections[sec]['chapters'][ch].append((verse, text))
    return sections


def generate_org_two_level(meta, chapters):
    """Generate Org-mode content for a two-level text."""
    lines = []
    lines.append(f'#+TITLE: {meta["title"]}')
    lines.append(f'#+AUTHOR: {meta["author"]}')
    lines.append('#+SETUPFILE: ../../public/themes/org/theme-readtheorg-local.setup')
    lines.append('#+OPTIONS: ^:t num:nil html-style:nil date:nil html-postamble:nil')
    lines.append('#+startup: overview')
    lines.append(f'#+EXPORT_FILE_NAME: ../../public/gr/{meta["stem"]}')
    lines.append('#+LANGUAGE: el')
    lines.append('')

    for ch_num, verses in chapters.items():
        # Chapter heading
        if ch_num == 0:
            heading = CHAPTER_ZERO_HEADING
        else:
            heading = f'Κεφάλαιον {ch_num}'
        lines.append(f'* {heading}')
        lines.append(':PROPERTIES:')
        lines.append(f':CUSTOM_ID: ch-{ch_num}')
        lines.append(':END:')
        lines.append('')

        for verse_num, text in verses:
            # Verse sub-heading
            lines.append(f'** Τμῆμα {verse_num}')
            lines.append(':PROPERTIES:')
            lines.append(f':CUSTOM_ID: ch-{ch_num}-sec-{verse_num}')
            lines.append(':END:')
            lines.append(text)
            lines.append('')

    return '\n'.join(lines)


def generate_org_three_level(meta, sections):
    """Generate Org-mode content for the Shepherd of Hermas (three-level)."""
    lines = []
    lines.append(f'#+TITLE: {meta["title"]}')
    lines.append(f'#+AUTHOR: {meta["author"]}')
    lines.append('#+SETUPFILE: ../../public/themes/org/theme-readtheorg-local.setup')
    lines.append('#+OPTIONS: ^:t num:nil html-style:nil date:nil html-postamble:nil')
    lines.append('#+startup: overview')
    lines.append(f'#+EXPORT_FILE_NAME: ../../public/gr/{meta["stem"]}')
    lines.append('#+LANGUAGE: el')
    lines.append('')

    for sec_num, sec_data in sections.items():
        # Section heading (Vision/Mandate/Parable title)
        title = sec_data['title'] or f'Τμῆμα {sec_num}'
        lines.append(f'* {title}')
        lines.append(':PROPERTIES:')
        lines.append(f':CUSTOM_ID: sec-{sec_num}')
        lines.append(':END:')
        lines.append('')

        for ch_num, verses in sec_data['chapters'].items():
            # Chapter heading within section
            lines.append(f'** Κεφάλαιον {ch_num}')
            lines.append(':PROPERTIES:')
            lines.append(f':CUSTOM_ID: sec-{sec_num}-ch-{ch_num}')
            lines.append(':END:')
            lines.append('')

            for verse_num, text in verses:
                # Verse sub-heading
                lines.append(f'*** Τμῆμα {verse_num}')
                lines.append(':PROPERTIES:')
                lines.append(f':CUSTOM_ID: sec-{sec_num}-ch-{ch_num}-sec-{verse_num}')
                lines.append(':END:')
                lines.append(text)
                lines.append('')

    return '\n'.join(lines)


def convert_text(source_path, meta, output_dir, dry_run=False):
    """Convert a single text file to Org-mode format.

    Returns output path on success, None on skip/error.
    """
    if meta.get('three_level'):
        data = parse_three_level(source_path)
        content = generate_org_three_level(meta, data)
    else:
        data = parse_two_level(source_path)
        content = generate_org_two_level(meta, data)

    output_path = os.path.join(output_dir, meta['stem'] + '.org')

    if dry_run:
        # Count sections for preview
        if meta.get('three_level'):
            sections = len(data)
            chapters = sum(len(s['chapters']) for s in data.values())
            verses = sum(
                len(v)
                for s in data.values()
                for v in s['chapters'].values()
            )
            print(f'  {meta["stem"]}.org: {sections} sections, '
                  f'{chapters} chapters, {verses} verses')
        else:
            chapters = len(data)
            verses = sum(len(v) for v in data.values())
            print(f'  {meta["stem"]}.org: {chapters} chapters, {verses} verses')
        return output_path

    os.makedirs(output_dir, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(content)

    return output_path


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Preview conversion without writing files',
    )
    parser.add_argument(
        '--output-dir', type=str, default=None,
        help='Output directory (default: sources/apostolic-fathers/gr/)',
    )
    parser.add_argument(
        '--source-dir', type=str, default=None,
        help='Source texts directory (default: sources/apostolic-fathers/texts/)',
    )
    args = parser.parse_args()

    # Resolve directories
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(script_dir)

    source_dir = args.source_dir or os.path.join(
        root_dir, 'sources', 'apostolic-fathers', 'texts')
    output_dir = args.output_dir or os.path.join(
        root_dir, 'sources', 'apostolic-fathers', 'gr')

    if not os.path.isdir(source_dir):
        print(f'Source directory not found: {source_dir}', file=sys.stderr)
        sys.exit(1)

    converted = 0
    skipped = 0

    for filename, meta in TEXTS.items():
        source_path = os.path.join(source_dir, filename)
        if not os.path.isfile(source_path):
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
