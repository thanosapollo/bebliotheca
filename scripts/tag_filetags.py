#!/usr/bin/env python3
"""Insert or update #+FILETAGS: in .org files based on author classification.

Scans content/{gr,en,la}/ for .org files, resolves the author slug from
the filename (title--author-slug.org) or STEM_OVERRIDES (for manually
curated files), and inserts a #+FILETAGS: line with era + century tags.

Usage:
    python3 scripts/tag_filetags.py              # Tag untagged files
    python3 scripts/tag_filetags.py --dry-run    # Preview only
    python3 scripts/tag_filetags.py --update     # Add century to era-only files
"""

import argparse
import glob
import os
import re
import sys

# ── Century pattern ──────────────────────────────────────────────────
CENTURY_RE = re.compile(r'^\d+c-(bc|ad)$')

# ── Author slug → era tag ───────────────────────────────────────────
# Tags follow Constantinople's classification system.
AUTHOR_TAGS = {
    # classical: Pre-Christian Greek & Latin (~800 BC - ~1 BC)
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

    # imperial: Roman-era secular literature (~1 AD - ~400 AD)
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

    # patristic: Church Fathers (~1 AD - ~750 AD)
    # Greek
    'clement-of-rome': 'patristic',
    'clement-of-alexandria': 'patristic',
    'barnabas': 'patristic',
    'ignatius-of-antioch': 'patristic',
    'polycarp-of-smyrna': 'patristic',
    'twelve-apostles': 'patristic',
    'hermas': 'patristic',
    'church-of-smyrna': 'patristic',
    'mathetes': 'patristic',
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

    # byzantine: Medieval Roman/Byzantine (~500 AD - 1453 AD)
    # Greek
    'procopius': 'byzantine',
    'joannes-zonaras': 'byzantine',
    'nonnus-of-panopolis': 'byzantine',
    'proclus': 'byzantine',
    'julian-the-emperor': 'byzantine',
    'anna-komnene': 'byzantine',
    'niketas-choniates': 'byzantine',
    'george-cedrenus': 'byzantine',
    'michael-psellos': 'byzantine',
    # Latin
    'ausonius-decimus-magnus': 'byzantine',
    'claudian': 'byzantine',

    # scripture: Biblical texts
    'new-testament': 'scripture',
}

# ── Author slug → century (floruit) ─────────────────────────────────
AUTHOR_CENTURIES = {
    # Classical Greek
    'homer': '8c-bc',
    'hesiod': '7c-bc',
    'pindar': '5c-bc',
    'aeschylus': '5c-bc',
    'sophocles': '5c-bc',
    'euripides': '5c-bc',
    'aristophanes': '5c-bc',
    'thucydides': '5c-bc',
    'herodotus': '5c-bc',
    'plato': '4c-bc',
    'aristotle': '4c-bc',
    'demosthenes': '4c-bc',
    'lysias': '5c-bc',
    'isocrates': '4c-bc',
    'isaeus': '4c-bc',
    'hippocrates': '5c-bc',
    'xenophon': '4c-bc',
    'bacchylides': '5c-bc',
    'apollonius-rhodius': '3c-bc',
    'callimachus': '3c-bc',
    'theocritus': '3c-bc',
    'moschus': '2c-bc',
    'bion-of-phlossa': '2c-bc',
    'theophrastus': '4c-bc',
    'hyperides': '4c-bc',
    'andocides': '5c-bc',
    'antiphon': '5c-bc',
    'dinarchus': '4c-bc',
    'aeschines': '4c-bc',
    'demades': '4c-bc',
    'lycurgus': '4c-bc',
    'euclid': '3c-bc',
    'parthenius': '1c-bc',
    'aratus-solensis': '3c-bc',
    'lycophron': '3c-bc',
    'apollodorus': '2c-bc',
    'harpocration-valerius': '2c-ad',
    'pseudo-plutarch': '2c-ad',
    # Classical Latin
    'lucretius': '1c-bc',
    'c-valerius-catullus': '1c-bc',
    'p-vergilius-maro': '1c-bc',
    'q-horatius-flaccus': '1c-bc',
    'p-ovidius-naso': '1c-bc',
    'julius-caesar': '1c-bc',
    'm-tullius-cicero': '1c-bc',
    'cornelius-nepos': '1c-bc',
    'sallust': '1c-bc',
    'titus-livius-livy': '1c-bc',
    'tibullus': '1c-bc',
    'sextus-propertius': '1c-bc',
    't-maccius-plautus': '3c-bc',
    'publius-terentius-afer-terence': '2c-bc',
    'sulpicia': '1c-bc',
    'q-tullius-cicero': '1c-bc',
    'vitruvius-pollio': '1c-bc',
    # Imperial Greek
    'plutarch': '1c-ad',
    'marcus-aurelius': '2c-ad',
    'lucian': '2c-ad',
    'lucian-of-samosata': '2c-ad',
    'arrian': '2c-ad',
    'diogenes-laertius': '3c-ad',
    'epictetus': '1c-ad',
    'strabo': '1c-bc',
    'pausanias': '2c-ad',
    'diodorus-siculus': '1c-bc',
    'polybius': '2c-bc',
    'cassius-dio-cocceianus': '3c-ad',
    'appian-of-alexandria': '2c-ad',
    'flavius-josephus': '1c-ad',
    'dio-chrysostom': '1c-ad',
    'galen': '2c-ad',
    'aelius-aristides': '2c-ad',
    'aelian': '3c-ad',
    'athenaeus': '3c-ad',
    'callistratus': '3c-ad',
    'chariton': '1c-ad',
    'xenophon-of-ephesus': '2c-ad',
    'longus': '2c-ad',
    'achilles-tatius': '2c-ad',
    'claudius-ptolemy': '2c-ad',
    'aretaeus-of-cappadocia': '2c-ad',
    'asclepiodotus': '1c-bc',
    'demetrius-of-phaleron': '4c-bc',
    'onasander': '1c-ad',
    'aeneas-tacticus': '4c-bc',
    'longinus': '1c-ad',
    'philostratus-sophista': '3c-ad',
    'philostratus-the-athenian': '3c-ad',
    'philostratus-minor': '3c-ad',
    'oppian': '2c-ad',
    'oppian-of-apamea': '3c-ad',
    'quintus-smyrnaeus': '4c-ad',
    'tryphiodorus': '3c-ad',
    'colluthus': '5c-ad',
    'dionysius-of-halicarnassus': '1c-bc',
    'agathemerus': '3c-ad',
    # Imperial Latin
    'seneca-lucius-annaeus': '1c-ad',
    'seneca-the-elder': '1c-ad',
    'cornelius-tacitus': '1c-ad',
    'pliny-the-elder': '1c-ad',
    'pliny-the-younger': '1c-ad',
    'juvenal': '2c-ad',
    'martial': '1c-ad',
    'petronius': '1c-ad',
    'suetonius': '2c-ad',
    'curtius-rufus-quintus': '1c-ad',
    'm-annaeus-lucanus': '1c-ad',
    'p-papinius-statius': '1c-ad',
    'silius-italicus': '1c-ad',
    'valerius-flaccus': '1c-ad',
    'valerius-maximus': '1c-ad',
    'aulus-gellius': '2c-ad',
    'florus-lucius-annaeus': '2c-ad',
    'apuleius': '2c-ad',
    'phaedrus': '1c-ad',
    'persius': '1c-ad',
    'quintilian': '1c-ad',
    'columella': '1c-ad',
    'celsus': '1c-ad',
    'ammianus-marcellinus': '4c-ad',
    # Patristic Greek
    'clement-of-rome': '1c-ad',
    'clement-of-alexandria': '2c-ad',
    'barnabas': '1c-ad',
    'ignatius-of-antioch': '2c-ad',
    'polycarp-of-smyrna': '2c-ad',
    'twelve-apostles': '1c-ad',
    'hermas': '2c-ad',
    'church-of-smyrna': '2c-ad',
    'mathetes': '2c-ad',
    'eusebius-of-caesarea': '4c-ad',
    'basil-saint-bishop-of-caesarea': '4c-ad',
    'john-of-damascus': '8c-ad',
    # Patristic Latin
    'jerome-saint': '4c-ad',
    'tertullian': '2c-ad',
    'minucius-felix': '2c-ad',
    'prudentius': '4c-ad',
    'boethius': '6c-ad',
    'augustinus': '4c-ad',
    # Byzantine Greek
    'procopius': '6c-ad',
    'joannes-zonaras': '12c-ad',
    'nonnus-of-panopolis': '5c-ad',
    'proclus': '5c-ad',
    'julian-the-emperor': '4c-ad',
    'anna-komnene': '12c-ad',
    'niketas-choniates': '12c-ad',
    'george-cedrenus': '11c-ad',
    'michael-psellos': '11c-ad',
    # Byzantine Latin
    'ausonius-decimus-magnus': '4c-ad',
    'claudian': '4c-ad',
    # Scripture omitted - Ἁγία Γραφή stands outside secular chronology
}

# ── Stem overrides for manually curated files (no --slug naming) ─────
STEM_OVERRIDES = {
    'agiagrafi': 'new-testament',
    'alcestis': 'euripides',
    'alexiada': 'anna-komnene',
    'argonautica': 'apollonius-rhodius',
    'bios-kai-gnomai': 'diogenes-laertius',
    'choniates': 'niketas-choniates',
    'compendium-chronicum': 'george-cedrenus',
    'confessiones': 'augustinus',
    'cyclops-play': 'euripides',
    'homeric-epigrams': 'homer',
    'iliad': 'homer',
    'marcus-aurelius-meditations': 'marcus-aurelius',
    'odyssey': 'homer',
    'psellos-chronographia': 'michael-psellos',
    'theocritus-epigrams': 'theocritus',
    'thucydides-history': 'thucydides',
}


def resolve_slug(path):
    """Resolve author slug from filename.

    For 'title--author-slug.org' files, extracts slug after '--'.
    For manual files without '--', looks up stem in STEM_OVERRIDES.

    Returns (slug_or_None, stem).
    """
    stem = os.path.splitext(os.path.basename(path))[0]
    if '--' in stem:
        return stem.rsplit('--', 1)[1], stem
    return STEM_OVERRIDES.get(stem), stem


def parse_filetags(line):
    """Parse tag names from a #+FILETAGS: line. Returns list of strings."""
    # Format: #+FILETAGS: :tag1:tag2:
    value = re.split(r'(?i)#\+filetags:\s*', line, maxsplit=1)
    if len(value) < 2:
        return []
    return [t for t in value[1].strip().split(':') if t]


def has_century_tag(tags):
    """Check if any tag in the list is a century tag."""
    return any(CENTURY_RE.match(t) for t in tags)


def build_filetags_value(slug):
    """Build the FILETAGS value string from an author slug.

    Returns string like ':classical:8c-bc:' or ':classical:', or None
    if the slug is unknown.
    """
    era = AUTHOR_TAGS.get(slug)
    if era is None:
        return None
    century = AUTHOR_CENTURIES.get(slug)
    if century:
        return f':{era}:{century}:'
    return f':{era}:'


def tag_file(path, dry_run=False, update=False):
    """Insert or update #+FILETAGS: based on author classification.

    Normal mode: Insert FILETAGS (era + century) if none exists.
    Update mode: Add century tag to files that only have an era tag.

    Returns:
        ('tagged', value)           - new FILETAGS inserted
        ('updated', value)          - century added to existing era tag
        ('skipped_existing',)       - already has FILETAGS (normal mode)
        ('skipped_has_century',)    - already has a century tag (update mode)
        ('skipped_no_century',)     - no century data for this author
        ('skipped_unknown', slug)   - author slug not in AUTHOR_TAGS
        ('skipped_no_slug',)        - cannot determine author slug
    """
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Resolve author slug
    slug, stem = resolve_slug(path)
    if slug is None:
        return ('skipped_no_slug',)

    if slug not in AUTHOR_TAGS:
        return ('skipped_unknown', slug)

    # Find existing #+FILETAGS: line (uppercase canonical form)
    existing_idx = None
    existing_tags = []
    for i, line in enumerate(lines):
        if line.startswith('#+FILETAGS:'):
            existing_idx = i
            existing_tags = parse_filetags(line)
            break

    if existing_idx is not None:
        # FILETAGS already exists
        if not update:
            return ('skipped_existing',)

        # --update mode: add century if missing
        if has_century_tag(existing_tags):
            return ('skipped_has_century',)

        century = AUTHOR_CENTURIES.get(slug)
        if not century:
            return ('skipped_no_century',)

        # Build new value: keep existing era tags, append century
        era_tags = [t for t in existing_tags if not CENTURY_RE.match(t)]
        new_value = ':' + ':'.join(era_tags + [century]) + ':'

        if not dry_run:
            lines[existing_idx] = f'#+FILETAGS: {new_value}\n'
            with open(path, 'w', encoding='utf-8') as f:
                f.writelines(lines)

        return ('updated', new_value)

    # No FILETAGS exists - insert after #+AUTHOR:
    filetags_value = build_filetags_value(slug)
    if filetags_value is None:
        return ('skipped_unknown', slug)

    new_lines = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if not inserted and (line.startswith('#+AUTHOR:') or line.startswith('#+author:')):
            new_lines.append(f'#+FILETAGS: {filetags_value}\n')
            inserted = True

    if not inserted:
        # No AUTHOR line found - insert after first line as fallback
        new_lines.insert(1, f'#+FILETAGS: {filetags_value}\n')

    if not dry_run:
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)

    return ('tagged', filetags_value)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without modifying files')
    parser.add_argument('--update', action='store_true',
                        help='Add century tags to files with era-only tags')
    args = parser.parse_args()

    content_dirs = ['content/gr', 'content/en', 'content/la']
    files = []
    for d in content_dirs:
        files.extend(sorted(glob.glob(f'{d}/*.org')))

    if not files:
        print('No .org files found in content/{gr,en,la}/', file=sys.stderr)
        sys.exit(1)

    tagged = 0
    updated = 0
    skipped_existing = 0
    skipped_has_century = 0
    skipped_no_century = 0
    skipped_unknown = 0
    skipped_no_slug = 0
    unknown_slugs = set()

    for path in files:
        result = tag_file(path, dry_run=args.dry_run, update=args.update)
        if result[0] == 'tagged':
            tagged += 1
            if args.dry_run:
                print(f'  [new] {path}: {result[1]}')
        elif result[0] == 'updated':
            updated += 1
            if args.dry_run:
                print(f'  [upd] {path}: {result[1]}')
        elif result[0] == 'skipped_existing':
            skipped_existing += 1
        elif result[0] == 'skipped_has_century':
            skipped_has_century += 1
        elif result[0] == 'skipped_no_century':
            skipped_no_century += 1
        elif result[0] == 'skipped_unknown':
            skipped_unknown += 1
            unknown_slugs.add(result[1])
        elif result[0] == 'skipped_no_slug':
            skipped_no_slug += 1

    mode = 'Would' if args.dry_run else 'Did'
    parts = []
    if tagged:
        parts.append(f'tag {tagged}')
    if updated:
        parts.append(f'update {updated}')
    if not parts:
        parts.append('change 0')

    skip_parts = []
    if skipped_existing:
        skip_parts.append(f'{skipped_existing} already tagged')
    if skipped_has_century:
        skip_parts.append(f'{skipped_has_century} already have century')
    if skipped_no_century:
        skip_parts.append(f'{skipped_no_century} no century data')
    if skipped_unknown:
        skip_parts.append(f'{skipped_unknown} unknown author')
    if skipped_no_slug:
        skip_parts.append(f'{skipped_no_slug} no author slug')

    summary = f'{mode} {", ".join(parts)} files'
    if skip_parts:
        summary += f'; skipped {", ".join(skip_parts)}'
    print(summary + '.')

    if unknown_slugs:
        print(f'Unknown author slugs: {", ".join(sorted(unknown_slugs))}')


if __name__ == '__main__':
    main()
