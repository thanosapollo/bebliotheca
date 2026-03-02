#!/usr/bin/env python3
"""Insert #+FILETAGS: into .org files based on author classification.

Scans content/{gr,en,la}/ for .org files, extracts the author slug from
the filename (title--author-slug.org), and inserts a #+FILETAGS: line
after #+AUTHOR: if none exists. Already-tagged files are skipped to
preserve manual curation.

Usage:
    python3 scripts/tag_filetags.py              # Apply changes
    python3 scripts/tag_filetags.py --dry-run    # Preview only
"""

import argparse
import glob
import os
import re
import sys

# Author slug → tag mapping.
# Tags follow Constantinople's classification system.
AUTHOR_TAGS = {
    # classical: Pre-Christian Greek & Latin (~800 BC – ~1 BC)
    # Greek
    'homer': 'classical',
    'hesiod': 'classical',
    'pindar': 'classical',
    'aeschylus': 'classical',
    'sophocles': 'classical',
    'euripides': 'classical',
    'aristophanes': 'classical',
    'thucydides': 'classical',
    'herodotus': 'classical',
    'plato': 'classical',
    'aristotle': 'classical',
    'demosthenes': 'classical',
    'lysias': 'classical',
    'isocrates': 'classical',
    'isaeus': 'classical',
    'hippocrates': 'classical',
    'xenophon': 'classical',
    'bacchylides': 'classical',
    'apollonius-rhodius': 'classical',
    'callimachus': 'classical',
    'theocritus': 'classical',
    'moschus': 'classical',
    'bion-of-phlossa': 'classical',
    'theophrastus': 'classical',
    'hyperides': 'classical',
    'andocides': 'classical',
    'antiphon': 'classical',
    'dinarchus': 'classical',
    'aeschines': 'classical',
    'demades': 'classical',
    'lycurgus': 'classical',
    'euclid': 'classical',
    'parthenius': 'classical',
    'aratus-solensis': 'classical',
    'lycophron': 'classical',
    'apollodorus': 'classical',
    'harpocration-valerius': 'classical',
    'pseudo-plutarch': 'classical',
    # Latin
    'lucretius': 'classical',
    'c-valerius-catullus': 'classical',
    'p-vergilius-maro': 'classical',
    'q-horatius-flaccus': 'classical',
    'p-ovidius-naso': 'classical',
    'julius-caesar': 'classical',
    'm-tullius-cicero': 'classical',
    'cornelius-nepos': 'classical',
    'sallust': 'classical',
    'titus-livius-livy': 'classical',
    'tibullus': 'classical',
    'sextus-propertius': 'classical',
    't-maccius-plautus': 'classical',
    'publius-terentius-afer-terence': 'classical',
    'sulpicia': 'classical',
    'q-tullius-cicero': 'classical',
    'vitruvius-pollio': 'classical',

    # imperial: Roman-era secular literature (~1 AD – ~400 AD)
    # Greek
    'plutarch': 'imperial',
    'marcus-aurelius': 'imperial',
    'lucian': 'imperial',
    'lucian-of-samosata': 'imperial',
    'arrian': 'imperial',
    'diogenes-laertius': 'imperial',
    'epictetus': 'imperial',
    'strabo': 'imperial',
    'pausanias': 'imperial',
    'diodorus-siculus': 'imperial',
    'polybius': 'imperial',
    'cassius-dio-cocceianus': 'imperial',
    'appian-of-alexandria': 'imperial',
    'flavius-josephus': 'imperial',
    'dio-chrysostom': 'imperial',
    'galen': 'imperial',
    'aelius-aristides': 'imperial',
    'aelian': 'imperial',
    'athenaeus': 'imperial',
    'callistratus': 'imperial',
    'chariton': 'imperial',
    'xenophon-of-ephesus': 'imperial',
    'longus': 'imperial',
    'achilles-tatius': 'imperial',
    'claudius-ptolemy': 'imperial',
    'aretaeus-of-cappadocia': 'imperial',
    'asclepiodotus': 'imperial',
    'demetrius-of-phaleron': 'imperial',
    'onasander': 'imperial',
    'aeneas-tacticus': 'imperial',
    'longinus': 'imperial',
    'philostratus-sophista': 'imperial',
    'philostratus-the-athenian': 'imperial',
    'philostratus-minor': 'imperial',
    'oppian': 'imperial',
    'oppian-of-apamea': 'imperial',
    'quintus-smyrnaeus': 'imperial',
    'tryphiodorus': 'imperial',
    'colluthus': 'imperial',
    'dionysius-of-halicarnassus': 'imperial',
    'agathemerus': 'imperial',
    # Latin
    'seneca-lucius-annaeus': 'imperial',
    'seneca-the-elder': 'imperial',
    'cornelius-tacitus': 'imperial',
    'pliny-the-elder': 'imperial',
    'pliny-the-younger': 'imperial',
    'juvenal': 'imperial',
    'martial': 'imperial',
    'petronius': 'imperial',
    'suetonius': 'imperial',
    'curtius-rufus-quintus': 'imperial',
    'm-annaeus-lucanus': 'imperial',
    'p-papinius-statius': 'imperial',
    'silius-italicus': 'imperial',
    'valerius-flaccus': 'imperial',
    'valerius-maximus': 'imperial',
    'aulus-gellius': 'imperial',
    'florus-lucius-annaeus': 'imperial',
    'apuleius': 'imperial',
    'phaedrus': 'imperial',
    'persius': 'imperial',
    'quintilian': 'imperial',
    'columella': 'imperial',
    'celsus': 'imperial',
    'ammianus-marcellinus': 'imperial',

    # patristic: Church Fathers (~1 AD – ~750 AD)
    # Greek
    'clement-of-alexandria': 'patristic',
    'barnabas': 'patristic',
    'eusebius-of-caesarea': 'patristic',
    'basil-saint-bishop-of-caesarea': 'patristic',
    'john-of-damascus': 'patristic',
    # Latin
    'jerome-saint': 'patristic',
    'tertullian': 'patristic',
    'minucius-felix': 'patristic',
    'prudentius': 'patristic',
    'boethius': 'patristic',
    'augustinus': 'patristic',

    # byzantine: Medieval Roman/Byzantine (~500 AD – 1453 AD)
    # Greek
    'procopius': 'byzantine',
    'joannes-zonaras': 'byzantine',
    'nonnus-of-panopolis': 'byzantine',
    'proclus': 'byzantine',
    'julian-the-emperor': 'byzantine',
    # Latin
    'ausonius-decimus-magnus': 'byzantine',
    'claudian': 'byzantine',

    # scripture: Biblical texts
    'new-testament': 'scripture',
}


def extract_author_slug(filename):
    """Extract author slug from 'title--author-slug.org' filename."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    if '--' in stem:
        return stem.rsplit('--', 1)[1]
    return None


def tag_file(path, dry_run=False):
    """Insert #+FILETAGS: after #+AUTHOR: if not already present.

    Returns: ('tagged', tag) | ('skipped_existing',) | ('skipped_unknown', slug) | ('skipped_no_slug',)
    """
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Check if FILETAGS already exists
    for line in lines:
        if line.startswith('#+FILETAGS:') or line.startswith('#+filetags:'):
            return ('skipped_existing',)

    # Extract author slug
    slug = extract_author_slug(path)
    if slug is None:
        return ('skipped_no_slug',)

    tag = AUTHOR_TAGS.get(slug)
    if tag is None:
        return ('skipped_unknown', slug)

    # Find #+AUTHOR: line and insert after it
    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if not inserted and (line.startswith('#+AUTHOR:') or line.startswith('#+author:')):
            new_lines.append(f'#+FILETAGS: :{tag}:\n')
            inserted = True

    if not inserted:
        # No AUTHOR line found — insert after first line as fallback
        new_lines.insert(1, f'#+FILETAGS: :{tag}:\n')

    if not dry_run:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

    return ('tagged', tag)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without modifying files')
    args = parser.parse_args()

    content_dirs = ['content/gr', 'content/en', 'content/la']
    files = []
    for d in content_dirs:
        files.extend(sorted(glob.glob(f'{d}/*.org')))

    if not files:
        print('No .org files found in content/{gr,en,la}/', file=sys.stderr)
        sys.exit(1)

    tagged = 0
    skipped_existing = 0
    skipped_unknown = 0
    skipped_no_slug = 0
    unknown_slugs = set()

    for path in files:
        result = tag_file(path, dry_run=args.dry_run)
        if result[0] == 'tagged':
            tagged += 1
            if args.dry_run:
                print(f'  {path}: :{result[1]}:')
        elif result[0] == 'skipped_existing':
            skipped_existing += 1
        elif result[0] == 'skipped_unknown':
            skipped_unknown += 1
            unknown_slugs.add(result[1])
        elif result[0] == 'skipped_no_slug':
            skipped_no_slug += 1

    mode = 'Would tag' if args.dry_run else 'Tagged'
    print(f'{mode} {tagged} files, '
          f'skipped {skipped_existing} (already tagged), '
          f'skipped {skipped_unknown} (unknown author), '
          f'skipped {skipped_no_slug} (no author slug).')

    if unknown_slugs:
        print(f'Unknown author slugs: {", ".join(sorted(unknown_slugs))}')


if __name__ == '__main__':
    main()
