#!/usr/bin/env python3
"""Insert or update #+FILETAGS: in .org files based on author classification.

Scans content/{gr,en,la}/ for .org files, resolves the author slug from
the filename (title--author-slug.org) or STEM_OVERRIDES (for manually
curated files), and inserts a #+FILETAGS: line with era + century tags.

Usage:
    python3 scripts/tag_filetags.py              # Tag untagged files
    python3 scripts/tag_filetags.py --dry-run    # Preview only
    python3 scripts/tag_filetags.py --update     # Add century to era-only files
    python3 scripts/tag_filetags.py --pg-tags    # Add PG volume tags from manifest
"""

import argparse
import json
import re
import sys
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ── Century pattern ──────────────────────────────────────────────────
CENTURY_RE = re.compile(r'^\d+c-(bc|ad)$')


class Result(Enum):
    """Outcome of tagging a single file."""
    TAGGED = auto()
    UPDATED = auto()
    SKIPPED_EXISTING = auto()
    SKIPPED_HAS_CENTURY = auto()
    SKIPPED_NO_CENTURY = auto()
    SKIPPED_UNKNOWN = auto()
    SKIPPED_NO_SLUG = auto()


# ── Author slug => era tag ───────────────────────────────────────────
# Tags follow Constantinople's classification system.
AUTHOR_TAGS: Dict[str, str] = {
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
    'eunapius-of-sardis': 'imperial',
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
    # Greek (Apostolic / pre-existing)
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
    # Greek (Patrologia Graeca)
    'alexander-of-lycopolis': 'patristic',
    'ammonius-of-alexandria': 'patristic',
    'amphilochius-of-iconium': 'patristic',
    'apollinaris-of-laodicea': 'patristic',
    'aristides-of-athens': 'patristic',
    'ariston-of-pella': 'patristic',
    'asterius-of-amasea': 'patristic',
    'athanasius-of-alexandria': 'patristic',
    'athenagoras': 'patristic',
    'basil-of-caesarea': 'patristic',
    'constitutiones-apostolorum': 'patristic',
    'cyril-of-alexandria': 'patristic',
    'cyril-of-jerusalem': 'patristic',
    'didymus-the-blind': 'patristic',
    'diodorus-of-tarsus': 'patristic',
    'dionysius-areopagita': 'patristic',
    'epiphanius-of-salamis': 'patristic',
    'epistle-to-diognetus': 'patristic',
    'eudokia-augusta': 'patristic',
    'eusebius-of-emesa': 'patristic',
    'eustathius-of-antioch': 'patristic',
    'evagrius-ponticus': 'patristic',
    'gaius-romanus': 'patristic',
    'gennadius-of-constantinople': 'patristic',
    'georgius-peccator': 'patristic',
    'gregory-of-nazianzus': 'patristic',
    'gregory-of-nyssa': 'patristic',
    'gregory-thaumaturgus': 'patristic',
    'hegesippus': 'patristic',
    'hermias-philosophus': 'patristic',
    'hesychius-of-jerusalem': 'patristic',
    'hippolytus-of-rome': 'patristic',
    'irenaeus-of-lyon': 'patristic',
    'john-chrysostom': 'patristic',
    'john-of-antioch': 'patristic',
    'julius-africanus': 'patristic',
    'justin-martyr': 'patristic',
    'leontius-of-byzantium': 'patristic',
    'macarius-of-egypt': 'patristic',
    'marcellus-of-ancyra': 'patristic',
    'marcus-diaconus': 'patristic',
    'maximus-the-confessor': 'patristic',
    'melito-of-sardis': 'patristic',
    'nemesius-of-emesa': 'patristic',
    'nonnos-of-panopolis': 'patristic',
    'origen': 'patristic',
    'palladius-of-helenopolis': 'patristic',
    'papias': 'patristic',
    'peter-of-alexandria': 'patristic',
    'phileas-of-thmuis': 'patristic',
    'philostorgius': 'patristic',
    'polycrates-of-ephesus': 'patristic',
    'proclus-of-constantinople': 'patristic',
    'serapion-of-thmuis': 'patristic',
    'severianus-of-gabala': 'patristic',
    'socrates-scholasticus': 'patristic',
    'sozomen': 'patristic',
    'tatian': 'patristic',
    'theodoret-of-cyrrhus': 'patristic',
    'theodorus-of-heraclea': 'patristic',
    'theophilus-of-alexandria': 'patristic',
    'theophilus-of-antioch': 'patristic',
    'theophilus-of-caesarea': 'patristic',
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
    'anna-komnena': 'byzantine',
    'anna-komnene': 'byzantine',
    'niketas-choniates': 'byzantine',
    'george-cedrenus': 'byzantine',
    'michael-psellos': 'byzantine',
    # Greek (Patrologia Graeca)
    'agapetus-diaconus': 'byzantine',
    'agathias-scholasticus': 'byzantine',
    'alexander-monachus': 'byzantine',
    'anonymous-pg': 'byzantine',
    'antonius-hagiographus': 'byzantine',
    'arethas-of-caesarea': 'byzantine',
    'barlaam-of-calabria': 'byzantine',
    'chronicon-paschale': 'byzantine',
    'constantine-manasses': 'byzantine',
    'constantine-porphyrogenitus': 'byzantine',
    'cosmas-indicopleustes': 'byzantine',
    'eustathius-of-thessalonica': 'byzantine',
    'george-acropolites': 'byzantine',
    'george-choeroboscus': 'byzantine',
    'george-codinus': 'byzantine',
    'george-hamartolos': 'byzantine',
    'george-monachus-continuatus': 'byzantine',
    'george-of-pisidia': 'byzantine',
    'george-pachymeres': 'byzantine',
    'george-phrantzes': 'byzantine',
    'george-syncellus': 'byzantine',
    'gregory-of-cyprus': 'byzantine',
    'gregory-palamas': 'byzantine',
    'joel-chronographus': 'byzantine',
    'john-anagnostes': 'byzantine',
    'john-argyropoulos': 'byzantine',
    'john-cameniates': 'byzantine',
    'john-cananus': 'byzantine',
    'john-cantacuzenus': 'byzantine',
    'john-cinnamus': 'byzantine',
    'john-lydus': 'byzantine',
    'john-malalas': 'byzantine',
    'john-presbyter': 'byzantine',
    'john-scylitzes': 'byzantine',
    'john-zonaras': 'byzantine',
    'joseph-genesius': 'byzantine',
    'laonicus-chalcocondyles': 'byzantine',
    'leo-grammaticus': 'byzantine',
    'leo-presbyter': 'byzantine',
    'leo-the-deacon': 'byzantine',
    'michael-attaleiates': 'byzantine',
    'michael-glycas': 'byzantine',
    'michael-psellus': 'byzantine',
    'nicephorus-bryennius': 'byzantine',
    'nicephorus-gregoras': 'byzantine',
    'nicephorus-patriarch': 'byzantine',
    'nicephorus-phocas': 'byzantine',
    'nicetas-choniates': 'byzantine',
    'oecumenius': 'byzantine',
    'olympiodorus-of-alexandria': 'byzantine',
    'paul-the-silentiary': 'byzantine',
    'photius-of-constantinople': 'byzantine',
    'procopius-of-caesarea': 'byzantine',
    'procopius-of-gaza': 'byzantine',
    'symeon-magistrus': 'byzantine',
    'symeon-metaphrastes': 'byzantine',
    'symeon-of-thessalonica': 'byzantine',
    'symeon-the-new-theologian': 'byzantine',
    'theodore-prodromus': 'byzantine',
    'theodore-studite': 'byzantine',
    'theodosius-the-deacon': 'byzantine',
    'theodorus-lector': 'byzantine',
    'theophanes-kerameus': 'byzantine',
    'theophanes-the-confessor': 'byzantine',
    'theophylact-simocatta': 'byzantine',
    # Latin
    'ausonius-decimus-magnus': 'byzantine',
    'claudian': 'byzantine',

    # scripture: Biblical texts
    'new-testament': 'scripture',
}

# ── Author slug => century (floruit) ─────────────────────────────────
AUTHOR_CENTURIES: Dict[str, str] = {
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
    'anna-komnena': '12c-ad',
    'anna-komnene': '12c-ad',
    'niketas-choniates': '12c-ad',
    'george-cedrenus': '11c-ad',
    'michael-psellos': '11c-ad',
    # Byzantine Latin
    'ausonius-decimus-magnus': '4c-ad',
    'claudian': '4c-ad',
    # Patristic Greek (Patrologia Graeca)
    'alexander-of-lycopolis': '4c-ad',
    'ammonius-of-alexandria': '5c-ad',
    'amphilochius-of-iconium': '4c-ad',
    'apollinaris-of-laodicea': '4c-ad',
    'aristides-of-athens': '2c-ad',
    'ariston-of-pella': '2c-ad',
    'asterius-of-amasea': '4c-ad',
    'athanasius-of-alexandria': '4c-ad',
    'athenagoras': '2c-ad',
    'basil-of-caesarea': '4c-ad',
    'constitutiones-apostolorum': '4c-ad',
    'cyril-of-alexandria': '5c-ad',
    'cyril-of-jerusalem': '4c-ad',
    'didymus-the-blind': '4c-ad',
    'diodorus-of-tarsus': '4c-ad',
    'dionysius-areopagita': '5c-ad',
    'epiphanius-of-salamis': '4c-ad',
    'epistle-to-diognetus': '2c-ad',
    'eudokia-augusta': '5c-ad',
    'eusebius-of-emesa': '4c-ad',
    'eustathius-of-antioch': '4c-ad',
    'evagrius-ponticus': '4c-ad',
    'gaius-romanus': '3c-ad',
    'gennadius-of-constantinople': '5c-ad',
    'georgius-peccator': '5c-ad',
    'gregory-of-nazianzus': '4c-ad',
    'gregory-of-nyssa': '4c-ad',
    'gregory-thaumaturgus': '3c-ad',
    'hegesippus': '2c-ad',
    'hermias-philosophus': '2c-ad',
    'hesychius-of-jerusalem': '5c-ad',
    'hippolytus-of-rome': '3c-ad',
    'irenaeus-of-lyon': '2c-ad',
    'john-chrysostom': '4c-ad',
    'john-of-antioch': '5c-ad',
    'julius-africanus': '3c-ad',
    'justin-martyr': '2c-ad',
    'leontius-of-byzantium': '6c-ad',
    'macarius-of-egypt': '4c-ad',
    'marcellus-of-ancyra': '4c-ad',
    'marcus-diaconus': '5c-ad',
    'maximus-the-confessor': '7c-ad',
    'melito-of-sardis': '2c-ad',
    'nemesius-of-emesa': '4c-ad',
    'nonnos-of-panopolis': '5c-ad',
    'origen': '3c-ad',
    'palladius-of-helenopolis': '4c-ad',
    'papias': '2c-ad',
    'peter-of-alexandria': '3c-ad',
    'phileas-of-thmuis': '3c-ad',
    'philostorgius': '5c-ad',
    'polycrates-of-ephesus': '2c-ad',
    'proclus-of-constantinople': '5c-ad',
    'serapion-of-thmuis': '4c-ad',
    'severianus-of-gabala': '4c-ad',
    'socrates-scholasticus': '5c-ad',
    'sozomen': '5c-ad',
    'tatian': '2c-ad',
    'theodoret-of-cyrrhus': '5c-ad',
    'theodorus-of-heraclea': '4c-ad',
    'theophilus-of-alexandria': '4c-ad',
    'theophilus-of-antioch': '2c-ad',
    'theophilus-of-caesarea': '2c-ad',
    # Byzantine Greek (Patrologia Graeca)
    'agapetus-diaconus': '6c-ad',
    'agathias-scholasticus': '6c-ad',
    'alexander-monachus': '6c-ad',
    'anonymous-pg': '10c-ad',
    'antonius-hagiographus': '6c-ad',
    'arethas-of-caesarea': '10c-ad',
    'barlaam-of-calabria': '14c-ad',
    'chronicon-paschale': '7c-ad',
    'constantine-manasses': '12c-ad',
    'constantine-porphyrogenitus': '10c-ad',
    'cosmas-indicopleustes': '6c-ad',
    'eustathius-of-thessalonica': '12c-ad',
    'george-acropolites': '13c-ad',
    'george-choeroboscus': '9c-ad',
    'george-codinus': '15c-ad',
    'george-hamartolos': '9c-ad',
    'george-monachus-continuatus': '10c-ad',
    'george-of-pisidia': '7c-ad',
    'george-pachymeres': '13c-ad',
    'george-phrantzes': '15c-ad',
    'george-syncellus': '9c-ad',
    'gregory-of-cyprus': '13c-ad',
    'gregory-palamas': '14c-ad',
    'joel-chronographus': '13c-ad',
    'john-anagnostes': '15c-ad',
    'john-argyropoulos': '15c-ad',
    'john-cameniates': '10c-ad',
    'john-cananus': '15c-ad',
    'john-cantacuzenus': '14c-ad',
    'john-cinnamus': '12c-ad',
    'john-lydus': '6c-ad',
    'john-malalas': '6c-ad',
    'john-presbyter': '11c-ad',
    'john-scylitzes': '11c-ad',
    'john-zonaras': '12c-ad',
    'joseph-genesius': '10c-ad',
    'laonicus-chalcocondyles': '15c-ad',
    'leo-grammaticus': '10c-ad',
    'leo-presbyter': '10c-ad',
    'leo-the-deacon': '10c-ad',
    'michael-attaleiates': '11c-ad',
    'michael-glycas': '12c-ad',
    'michael-psellus': '11c-ad',
    'nicephorus-bryennius': '12c-ad',
    'nicephorus-gregoras': '14c-ad',
    'nicephorus-patriarch': '9c-ad',
    'nicephorus-phocas': '10c-ad',
    'nicetas-choniates': '12c-ad',
    'oecumenius': '6c-ad',
    'olympiodorus-of-alexandria': '6c-ad',
    'paul-the-silentiary': '6c-ad',
    'photius-of-constantinople': '9c-ad',
    'procopius-of-caesarea': '6c-ad',
    'procopius-of-gaza': '6c-ad',
    'symeon-magistrus': '10c-ad',
    'symeon-metaphrastes': '10c-ad',
    'symeon-of-thessalonica': '15c-ad',
    'symeon-the-new-theologian': '11c-ad',
    'theodore-prodromus': '12c-ad',
    'theodore-studite': '9c-ad',
    'theodosius-the-deacon': '8c-ad',
    'theodorus-lector': '6c-ad',
    'theophanes-kerameus': '12c-ad',
    'theophanes-the-confessor': '9c-ad',
    'theophylact-simocatta': '7c-ad',
    # Imperial (Patrologia Graeca)
    'eunapius-of-sardis': '4c-ad',
    # Scripture omitted
}

# ── Stem overrides for manually curated files (no --slug naming) ─────
STEM_OVERRIDES: Dict[str, str] = {
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


def resolve_slug(path: Path) -> Tuple[Optional[str], str]:
    """Resolve author slug from filename.

    For 'title--author-slug.org' files, extracts slug after '--'.
    For manual files without '--', looks up stem in STEM_OVERRIDES.

    Returns (slug_or_None, stem).
    """
    stem = path.stem
    if '--' in stem:
        return stem.rsplit('--', 1)[1], stem
    return STEM_OVERRIDES.get(stem), stem


def parse_filetags(line: str) -> List[str]:
    """Parse tag names from a #+FILETAGS: line. Returns list of strings."""
    value = re.split(r'(?i)#\+filetags:\s*', line, maxsplit=1)
    if len(value) < 2:
        return []
    return [t for t in value[1].strip().split(':') if t]


def has_century_tag(tags: List[str]) -> bool:
    """Check if any tag in the list is a century tag."""
    return any(CENTURY_RE.match(t) for t in tags)


def build_filetags_value(slug: str) -> Optional[str]:
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


def tag_file(
    path: Path,
    dry_run: bool = False,
    update: bool = False,
) -> Tuple[Result, Optional[str]]:
    """Insert or update #+FILETAGS: based on author classification.

    Normal mode: Insert FILETAGS (era + century) if none exists.
    Update mode: Add century tag to files that only have an era tag.

    Returns (Result, value_or_slug_or_None).
    """
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)

    slug, stem = resolve_slug(path)
    if slug is None:
        return Result.SKIPPED_NO_SLUG, None

    if slug not in AUTHOR_TAGS:
        return Result.SKIPPED_UNKNOWN, slug

    # Find existing #+FILETAGS: line
    existing_idx: Optional[int] = None
    existing_tags: List[str] = []
    for i, line in enumerate(lines):
        if line.startswith('#+FILETAGS:'):
            existing_idx = i
            existing_tags = parse_filetags(line)
            break

    if existing_idx is not None:
        if not update:
            return Result.SKIPPED_EXISTING, None

        # --update mode: add century if missing
        if has_century_tag(existing_tags):
            return Result.SKIPPED_HAS_CENTURY, None

        century = AUTHOR_CENTURIES.get(slug)
        if not century:
            return Result.SKIPPED_NO_CENTURY, None

        era_tags = [t for t in existing_tags if not CENTURY_RE.match(t)]
        new_value = ':' + ':'.join(era_tags + [century]) + ':'

        if not dry_run:
            lines[existing_idx] = f'#+FILETAGS: {new_value}\n'
            path.write_text(''.join(lines), encoding='utf-8')

        return Result.UPDATED, new_value

    # No FILETAGS exists - insert after #+AUTHOR:
    filetags_value = build_filetags_value(slug)
    if filetags_value is None:
        return Result.SKIPPED_UNKNOWN, slug

    new_lines: List[str] = []
    inserted = False
    for line in lines:
        new_lines.append(line)
        if not inserted and line.lower().startswith('#+author:'):
            new_lines.append(f'#+FILETAGS: {filetags_value}\n')
            inserted = True

    if not inserted:
        new_lines.insert(1, f'#+FILETAGS: {filetags_value}\n')

    if not dry_run:
        path.write_text(''.join(new_lines), encoding='utf-8')

    return Result.TAGGED, filetags_value


# ── PG volume tagging ──────────────────────────────────────────────

PG_SPEC_RE = re.compile(r'_\s*PG\s*(.+?)/')


def parse_pg_spec(spec: str) -> List[str]:
    """Parse a PG volume spec into a list of tag strings.

    Examples:
        '88'          => ['pg88']
        '47-64'       => ['pg47-64']
        '86a'         => ['pg86a']
        '86B'         => ['pg86b']
        '87a-87c'     => ['pg87a', 'pg87b', 'pg87c']
        '34,65'       => ['pg34', 'pg65']
        '105,111,117' => ['pg105', 'pg111', 'pg117']
        ' 25-28'      => ['pg25-28']
    """
    spec = spec.strip().lower()
    tags: List[str] = []

    # Split on comma first (composite specs)
    parts = [p.strip() for p in spec.split(',')]
    for part in parts:
        if not part:
            continue
        # Check for letter-suffix range: e.g. 87a-87c
        m = re.match(r'^(\d+)([a-z])-\d+([a-z])$', part)
        if m:
            num, start_letter, end_letter = m.group(1), m.group(2), m.group(3)
            for c in range(ord(start_letter), ord(end_letter) + 1):
                tags.append(f'pg{num}{chr(c)}')
            continue
        # Plain spec (single number, range, or number+letter)
        tags.append(f'pg{part}')

    return tags


def add_pg_tag_to_file(
    path: Path,
    pg_tags: List[str],
    dry_run: bool = False,
) -> Tuple[str, Optional[str]]:
    """Add PG volume tags to existing FILETAGS line.

    Returns (status, detail) where status is 'tagged', 'skipped_has_pg',
    'skipped_no_filetags', or 'error'.
    """
    try:
        text = path.read_text(encoding='utf-8')
    except OSError as e:
        return 'error', str(e)

    lines = text.splitlines(keepends=True)

    filetags_idx: Optional[int] = None
    existing_tags: List[str] = []
    for i, line in enumerate(lines):
        if line.startswith('#+FILETAGS:'):
            filetags_idx = i
            existing_tags = parse_filetags(line)
            break

    if filetags_idx is None:
        return 'skipped_no_filetags', None

    # Skip if any pg tag already present
    if any(t.startswith('pg') for t in existing_tags):
        return 'skipped_has_pg', None

    new_tags = existing_tags + pg_tags
    new_value = ':' + ':'.join(new_tags) + ':'

    if not dry_run:
        lines[filetags_idx] = f'#+FILETAGS: {new_value}\n'
        path.write_text(''.join(lines), encoding='utf-8')

    return 'tagged', new_value


def run_pg_tags(dry_run: bool = False) -> None:
    """Add PG volume tags to all PG Migne files using the PDF manifest."""
    manifest_path = Path('log/pg-migne-pdf-manifest.json')
    if not manifest_path.exists():
        print(f'Manifest not found: {manifest_path}', file=sys.stderr)
        sys.exit(1)

    manifest: Dict[str, str] = json.loads(
        manifest_path.read_text(encoding='utf-8'))

    content_gr = Path('content/gr')
    tagged = 0
    skipped_has_pg = 0
    skipped_no_filetags = 0
    skipped_not_found = 0
    errors = 0

    for org_name, pdf_path in sorted(manifest.items()):
        org_path = content_gr / org_name
        if not org_path.exists():
            skipped_not_found += 1
            continue

        m = PG_SPEC_RE.search(pdf_path)
        if not m:
            errors += 1
            print(f'  [err] No PG spec in path: {pdf_path}', file=sys.stderr)
            continue

        pg_tags = parse_pg_spec(m.group(1))
        if not pg_tags:
            errors += 1
            print(f'  [err] Empty tags for spec: {m.group(1)}', file=sys.stderr)
            continue

        status, detail = add_pg_tag_to_file(org_path, pg_tags, dry_run=dry_run)

        if status == 'tagged':
            tagged += 1
            if dry_run:
                print(f'  [pg] {org_name}: {detail}')
        elif status == 'skipped_has_pg':
            skipped_has_pg += 1
        elif status == 'skipped_no_filetags':
            skipped_no_filetags += 1
        elif status == 'error':
            errors += 1
            print(f'  [err] {org_name}: {detail}', file=sys.stderr)

    mode = 'Would tag' if dry_run else 'Tagged'
    print(f'{mode} {tagged} files with PG volume tags; '
          f'skipped {skipped_has_pg} (already have pg tags), '
          f'{skipped_no_filetags} (no FILETAGS line), '
          f'{skipped_not_found} (file not found); '
          f'{errors} errors.')


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--dry-run', action='store_true',
                        help='Preview changes without modifying files')
    parser.add_argument('--update', action='store_true',
                        help='Add century tags to files with era-only tags')
    parser.add_argument('--pg-tags', action='store_true',
                        help='Add PG volume tags from pg-migne-pdf-manifest.json')
    args = parser.parse_args()

    if args.pg_tags:
        run_pg_tags(dry_run=args.dry_run)
        return

    content_dirs = [Path('content') / d for d in ('gr', 'en', 'la')]
    files = [
        f
        for d in content_dirs
        if d.exists()
        for f in sorted(d.glob('*.org'))
    ]

    if not files:
        print('No .org files found in content/{gr,en,la}/', file=sys.stderr)
        sys.exit(1)

    # Accumulate results
    counts: Dict[Result, int] = {r: 0 for r in Result}
    unknown_slugs: set = set()

    for path in files:
        result, value = tag_file(path, dry_run=args.dry_run, update=args.update)
        counts[result] += 1

        if result == Result.TAGGED and args.dry_run:
            print(f'  [new] {path}: {value}')
        elif result == Result.UPDATED and args.dry_run:
            print(f'  [upd] {path}: {value}')
        elif result == Result.SKIPPED_UNKNOWN and value:
            unknown_slugs.add(value)

    # Summary
    mode = 'Would' if args.dry_run else 'Did'
    parts: List[str] = []
    if counts[Result.TAGGED]:
        parts.append(f'tag {counts[Result.TAGGED]}')
    if counts[Result.UPDATED]:
        parts.append(f'update {counts[Result.UPDATED]}')
    if not parts:
        parts.append('change 0')

    skip_parts: List[str] = []
    if counts[Result.SKIPPED_EXISTING]:
        skip_parts.append(f'{counts[Result.SKIPPED_EXISTING]} already tagged')
    if counts[Result.SKIPPED_HAS_CENTURY]:
        skip_parts.append(f'{counts[Result.SKIPPED_HAS_CENTURY]} already have century')
    if counts[Result.SKIPPED_NO_CENTURY]:
        skip_parts.append(f'{counts[Result.SKIPPED_NO_CENTURY]} no century data')
    if counts[Result.SKIPPED_UNKNOWN]:
        skip_parts.append(f'{counts[Result.SKIPPED_UNKNOWN]} unknown author')
    if counts[Result.SKIPPED_NO_SLUG]:
        skip_parts.append(f'{counts[Result.SKIPPED_NO_SLUG]} no author slug')

    summary = f'{mode} {", ".join(parts)} files'
    if skip_parts:
        summary += f'; skipped {", ".join(skip_parts)}'
    print(summary + '.')

    if unknown_slugs:
        print(f'Unknown author slugs: {", ".join(sorted(unknown_slugs))}')


if __name__ == '__main__':
    main()
