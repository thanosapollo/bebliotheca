#!/usr/bin/env python3
"""
Verify PG Migne volume tags against Roger Pearse's canonical index.

This script cross-references our catalog's pg volume tags with the authoritative
PG volume index to detect misattributions and ensure scholarly accuracy.
"""

import json
import re
from collections import defaultdict
from pathlib import Path

# Canonical PG volume assignments from Roger Pearse's index
# Format: author_key => (volume_range, note)
CANONICAL_PG_VOLUMES = {
    'clement_rome': ('1-2', 'Clemens Romanus, Pseudo-Clemens'),
    'barnabas': ('2', 'In PG 2 with Pseudo-Clement'),
    'hermas': ('2', 'Shepherd of Hermas'),
    'diognetus': ('2', 'Epistle to Diognetus'),
    'dionysius_areopagite': ('3-4', 'Pseudo-Dionysius + scholia'),
    'ignatius': ('5', 'With Polycarp, Melito, 2nd cent popes'),
    'polycarp': ('5', 'With Ignatius'),
    'melito': ('5', 'With Ignatius, Polycarp'),
    'justin': ('6', 'With Tatian, Athenagoras, Theophilus, Hermias'),
    'tatian': ('6', 'With Justin'),
    'athenagoras': ('6', 'With Justin'),
    'theophilus_antioch': ('6', 'With Justin'),
    'hermias': ('6', 'With Justin'),
    'irenaeus': ('7', 'Full volume'),
    'clement_alexandria': ('8-9', 'Complete works'),
    'gregory_thaumaturgus': ('10', 'With Hippolytus, Dionysius Alex, Julius Africanus'),
    'hippolytus': ('10,16/3', 'In PG 10 and Hexapla vol'),
    'dionysius_alexandria': ('10', 'With Gregory Thaum'),
    'julius_africanus': ('10', 'With Gregory Thaum'),
    'origen': ('11-17', 'Vols 1-7 plus Hexapla'),
    'methodius': ('18', 'With Peter of Alexandria, others'),
    'peter_alexandria': ('18', 'With Methodius'),
    'eusebius': ('19-24', 'Vols 1-6'),
    'athanasius': ('25-28', 'Vols 1-4'),
    'basil_great': ('29-32', 'Vols 1-4 + Eunomius'),
    'cyril_jerusalem': ('33', 'With Peter Alex, Timothy, Apollinaris, Diodorus'),
    'apollinaris': ('33', 'With Cyril Jerusalem'),
    'diodorus_tarsus': ('33', 'With Cyril Jerusalem'),
    'macarius_egypt': ('34', 'With Macarius Alex, Palladius'),
    'palladius': ('34,65', 'Lausiac History in 34; also in 65'),
    'gregory_nazianzus': ('35-38', 'Vols 1-4'),
    'didymus': ('39', 'With Amphilochius, Nectarius'),
    'amphilochius': ('39', 'With Didymus'),
    'evagrius': ('40', 'With Philo, Asterius, Nemesius, others'),
    'nemesius': ('40', 'With Evagrius'),
    'asterius_amasea': ('40', 'With Evagrius'),
    'epiphanius': ('41-43', 'Vols 1-3 + Nonnus'),
    'nonnus': ('43', 'With Epiphanius vol 3'),
    'gregory_nyssa': ('44-46', 'Vols 1-3'),
    'john_chrysostom': ('47-64', 'Vols 1.1-13'),
    'severian': ('56,63,65', 'Scattered in Chrysostom vols + 65'),
    'socrates': ('67', 'With Sozomen'),
    'sozomen': ('67', 'With Socrates'),
    'cyril_alexandria': ('68-77', 'Vols 1-10'),
    'isidore_pelusium': ('78', 'With Zosimus'),
    'nilus': ('79', 'With Hyperechius'),
    'theodoret': ('80-84', 'Vols 1-5'),
    'leontius_byzantium': ('86/1-2', 'Vols 1-2'),
    'procopius_gaza': ('87/1-3', 'Vols 1-3'),
    'john_climacus': ('88', 'With Cosmas Indicopleustes, Agathias'),
    'cosmas_indicopleustes': ('88', 'With John Climacus'),
    'agathias': ('88', 'With John Climacus'),
    'anastasius_sinai': ('89', 'With Anastasius Antioch, Antiochus Saba'),
    'maximus_confessor': ('90-91', 'Vols 1-2'),
    'chronicon_paschale': ('92', 'With George Pisidia'),
    'george_pisidia': ('92', 'With Chronicon Paschale'),
    'hesychius_jerusalem': ('93', 'With Olympiodorus, Leontius Neapolis'),
    'olympiodorus_alexandria': ('93', 'With Hesychius'),
    'john_damascene': ('94-96', 'Vols 1-3'),
    'john_malalas': ('97', 'With Andrew Crete, Theodore Abucara'),
    'andrew_crete': ('97', 'With John Malalas'),
    'germanus_constantinople': ('98', 'With Cosmas Jerusalem, others'),
    'theodore_studite': ('99', 'Full volume'),
    'nicephorus_constantinople': ('100', 'With Stephanus, Procopius, others'),
    'photius': ('101-104', 'Vols 1-4'),
    'nicetas_paphlagonia': ('105', 'With Nicetas Byzantinus, Theognostus'),
    'joseph_hymnographer': ('105-106', 'Scattered in 105-106'),
    'andrew_caesarea': ('106', 'With Arethas, others'),
    'arethas_caesarea': ('106', 'With Andrew'),
    'leo_emperor': ('107', 'Full volume'),
    'theophanes_confessor': ('108', 'With Leo Grammaticus, Anastasius'),
    'leo_grammaticus': ('108,111,120', 'Scattered'),
    'constantine_porphyrogenitus': ('109,112-113', 'Continuation of Theophanes + vols 1-2'),
    'george_monachus': ('110-111', 'Hamartolus chronicle + supplements'),
    'nicholas_constantinople': ('111', 'With Joseph Genesius, Leo Gram, others'),
    'joseph_genesius': ('109,111', 'Scattered in Constantine vols'),
    'symeon_metaphrastes': ('114-116', 'Vols 1-3'),
    'leo_deacon': ('117', 'With Basil Porphyrog, others'),
    'oecumenius': ('118-119', 'Vols 1-2'),
    'george_cedrenus': ('121-122', 'Compendium Historiarum vols 1-2'),
    'john_scylitzes': ('122', 'With Cedrenus vol 2, Psellus'),
    'michael_psellus': ('122', 'With Cedrenus vol 2'),
    'theophylact_bulgaria': ('123-126', 'Vols 1-4'),
    'nicephorus_bryennius': ('127', 'With Constantine Manasses, others'),
    'constantine_manasses': ('127', 'With Nicephorus Bryennius'),
    'euthymius_zigabenus': ('128-131', 'Vols 1-4 + Anna Comnena'),
    'anna_comnena': ('131', 'Alexiad with Euthymius vol 4'),
    'theophanes_kerameus': ('132', 'With Nilus Doxapatrius, John Antioch'),
    'john_cinnamus': ('133', 'With Manuel Comnenus, others'),
    'theodore_prodromus': ('133', 'With John Cinnamus'),
    'john_zonaras': ('134-135', 'Vols 1-2 + Eustathius'),
    'eustathius_thessalonica': ('135-136', 'Annales cont + works'),
    'theodore_balsamon': ('137-138', 'Vols 1-2'),
    'joel_chronographer': ('139', 'With Nicetas Choniates'),
    'nicetas_choniates': ('139-140', 'Historia + Thesaurus'),
    'michael_acominatus': ('141', 'With George Acropolites, others'),
    'george_acropolites': ('140,141', 'Letter in 140, works in 141'),
    'gregory_cyprus': ('142', 'With Athanasius Const, Nicephorus Blemmida'),
    'george_pachymeres': ('143-144', 'History vols 1-2'),
    'nicephorus_callistus': ('145-147', 'HE vols 1-3'),
    'nicephorus_gregoras': ('148-149', 'Historia vols 1-2'),
    'gregory_palamas': ('150-151', 'Vols 1-2 + opponents'),
    'john_cantacuzene': ('153-154', 'Historia vols 1-2'),
    'symeon_thessalonica': ('155', 'Full volume'),
    'manuel_ii': ('156', 'With Chrysoloras, Cananus, others'),
    'john_cananus': ('156', 'With Manuel II'),
    'george_phrantzes': ('156', 'With Manuel II'),
    'george_codinus': ('157', 'With Ducas'),
    'ducas': ('157', 'With Codinus'),
    'michael_glycas': ('158', 'With others'),
    'laonicus_chalcocondyles': ('159', 'With Leonardus, Isidore'),
    'gennadius_scholarius': ('160', 'With Pletho, others'),
    'bessarion': ('161', 'With Trapezuntius, Lascaris'),
}

# Greek author name normalization
AUTHOR_NORMALIZE = {
    'Ἀθανάσιος Ἀλεξανδρείας': 'athanasius',
    'Βασίλειος Καισαρείας': 'basil_great',
    'Γρηγόριος Ναζιανζοῦ': 'gregory_nazianzus',
    'Γρηγόριος Νύσσης': 'gregory_nyssa',
    'Γρηγόριος Παλαμᾶς': 'gregory_palamas',
    'Ἰωάννης Χρυσόστομος': 'john_chrysostom',
    'Κύριλλος Ἀλεξανδρείας': 'cyril_alexandria',
    'Κύριλλος Ἱεροσολύμων': 'cyril_jerusalem',
    'Κλήμης Ρώμης': 'clement_rome',
    'Κλήμης Ἀλεξανδρείας': 'clement_alexandria',
    'Εἰρηναῖος Λυών': 'irenaeus',
    'Ἰουστῖνος ὁ Μάρτυς': 'justin',
    'Ὠριγένης': 'origen',
    'Εὐσέβιος Καισαρείας': 'eusebius',
    'Ἐπιφάνιος Σαλαμῖνος': 'epiphanius',
    'Θεοδώρητος Κύρρου': 'theodoret',
    'Διονύσιος Ἀρεοπαγίτης': 'dionysius_areopagite',
    'Μάξιμος ὁ Ὁμολογητής': 'maximus_confessor',
    'Ἰωάννης Δαμασκηνός': 'john_damascene',
    'Φώτιος Κωνσταντινουπόλεως': 'photius',
    'Θεοφύλακτος Σιμοκάττης': 'theophylact_bulgaria',
    'Νικηφόρος Γρηγορᾶς': 'nicephorus_gregoras',
    'Νικηφόρος Κωνσταντινουπόλεως': 'nicephorus_constantinople',
    'Γεώργιος Κεδρηνός': 'george_cedrenus',
    'Μιχαὴλ Ψελλός': 'michael_psellus',
    'Ἄννα Κομνηνή': 'anna_comnena',
    'Νικήτας Χωνιάτης': 'nicetas_choniates',
    'Ἰωάννης Ζωναρᾶς': 'john_zonaras',
    'Γεώργιος Παχυμέρης': 'george_pachymeres',
    'Ἰωάννης Καντακουζηνός': 'john_cantacuzene',
    'Δίδυμος ὁ Τυφλός': 'didymus',
    'Ἀμφιλόχιος Ἰκονίου': 'amphilochius',
    'Εὐάγριος Ποντικός': 'evagrius',
    'Νεμέσιος Ἐμέσης': 'nemesius',
    'Γρηγόριος Θαυματουργός': 'gregory_thaumaturgus',
    'Ἰούλιος Ἀφρικανός': 'julius_africanus',
    'Πέτρος Ἀλεξανδρείας': 'peter_alexandria',
    'Σωκράτης Σχολαστικός': 'socrates',
    'Ἑρμείας Σωζομενός': 'sozomen',
    'Ἡσύχιος Ἱεροσολύμων': 'hesychius_jerusalem',
    'Ὀλυμπιόδωρος Διάκονος Ἀλεξανδρείας': 'olympiodorus_alexandria',
    'Θεοφάνης ὁ Ὁμολογητής': 'theophanes_confessor',
    'Γεώργιος Πισίδης': 'george_pisidia',
    'Χρονικὸν Πασχάλιον': 'chronicon_paschale',
    'Κοσμᾶς Ἰνδικοπλεύστης': 'cosmas_indicopleustes',
    'Ἀγαθίας Σχολαστικός': 'agathias',
    'Θεόδωρος Στουδίτης': 'theodore_studite',
    'Λέων Γραμματικός': 'leo_grammaticus',
    'Κωνσταντῖνος Πορφυρογέννητος': 'constantine_porphyrogenitus',
    'Γεώργιος Ἁμαρτωλός': 'george_monachus',
    'Συμεὼν Μεταφραστής': 'symeon_metaphrastes',
    'Λέων Διάκονος': 'leo_deacon',
    'Οἰκουμένιος': 'oecumenius',
    'Ἰωάννης Σκυλίτζης': 'john_scylitzes',
    'Εὐστάθιος Θεσσαλονίκης': 'eustathius_thessalonica',
    'Ἰωάννης Κίνναμος': 'john_cinnamus',
    'Θεόδωρος Πρόδρομος': 'theodore_prodromus',
    'Νικηφόρος Βρυέννιος': 'nicephorus_bryennius',
    'Κωνσταντῖνος Μανασσῆς': 'constantine_manasses',
    'Γεώργιος Ἀκροπολίτης': 'george_acropolites',
    'Θεοφάνης Κεραμεύς': 'theophanes_kerameus',
    'Ἰωὴλ Χρονογράφος': 'joel_chronographer',
    'Γρηγόριος Κύπριος': 'gregory_cyprus',
    'Μιχαὴλ Γλυκᾶς': 'michael_glycas',
    'Λαόνικος Χαλκοκονδύλης': 'laonicus_chalcocondyles',
    'Γεννάδιος Κωνσταντινουπόλεως': 'gennadius_scholarius',
    'Ἰωάννης Μαλάλας': 'john_malalas',
    'Ἰωάννης Κανανός': 'john_cananus',
    'Γεώργιος Φραντζῆς': 'george_phrantzes',
    'Παλλάδιος Ἑλενοπόλεως': 'palladius',
    'Μακάριος Αἰγύπτου': 'macarius_egypt',
    'Ἰγνάτιος Ἀντιοχείας': 'ignatius',
    'Πολύκαρπος Σμύρνης': 'polycarp',
    'Μελίτων Σάρδεων': 'melito',
    'Τατιανός': 'tatian',
    'Ἀθηναγόρας Ἀθηναῖος': 'athenagoras',
    'Θεόφιλος Ἀντιοχείας': 'theophilus_antioch',
    'Ἑρμείας Φιλόσοφος': 'hermias',
    'Βαρνάβας': 'barnabas',
    'Ποιμὴν τοῦ Ἑρμᾶ': 'hermas',
    'Πρὸς Διόγνητον': 'diognetus',
    'Ἀπολινάριος Λαοδικείας': 'apollinaris',
    'Διόδωρος Ταρσοῦ': 'diodorus_tarsus',
    'Νόννος Πανοπολίτης': 'nonnus',
    'Σεβηριανὸς Γαβάλων': 'severian',
    'Προκόπιος Καισαρείας': 'procopius_gaza',
    'Ἀστέριος Ἀμασείας': 'asterius_amasea',
    'Λέων Πρεσβύτερος': 'leo_presbyter',
    'Συμεὼν ὁ Νέος Θεολόγος': 'symeon_theologian',
    'Θεοφύλακτος Σιμοκάττης': 'theophylact_bulgaria',  # Note: could be confused with Simocatta
    'Γεώργιος Σύγκελλος': 'george_syncellus',
    'Συμεὼν Μάγιστρος': 'symeon_magister',
    'Βαρλαὰμ Καλαβρός': 'barlaam',
    'Θεοδόσιος Διάκονος': 'theodosius_deacon',
    'Νικηφόρος Φωκᾶς': 'nicephorus_phocas',
}


def parse_pg_tag(tag):
    """Parse pgXX or pgXX-YY into volume numbers."""
    if not tag.startswith('pg'):
        return []

    tag = tag[2:]  # Remove 'pg' prefix

    if '-' in tag and tag.replace('-', '').isdigit():
        # Range like pg47-64
        parts = tag.split('-')
        start, end = int(parts[0]), int(parts[1])
        return list(range(start, end + 1))
    elif '/' in tag:
        # Sub-volume like pg16/1
        return [tag]
    elif tag.isdigit():
        return [int(tag)]
    else:
        return []


def canonical_volumes_for_author(author_key):
    """Get expected PG volumes for an author."""
    if author_key not in CANONICAL_PG_VOLUMES:
        return None

    vol_str, note = CANONICAL_PG_VOLUMES[author_key]
    volumes = []

    for part in vol_str.split(','):
        part = part.strip()
        if '-' in part and '/' not in part:
            # Range like 47-64
            start, end = part.split('-')
            volumes.extend(range(int(start), int(end) + 1))
        elif '/' in part:
            # Sub-volume like 16/1
            volumes.append(part)
        else:
            volumes.append(int(part))

    return sorted(set(volumes)), note


def main():
    # Load catalog
    catalog_path = Path('/home/thanos/Dev/web/bebliotheca/public/catalog.json')
    with open(catalog_path) as f:
        data = json.load(f)
        catalog = data['works']

    # Extract PG works grouped by author
    by_author = defaultdict(list)
    for work in catalog:
        tags = work.get('tags', [])
        pg_tags = [t for t in tags if t.startswith('pg')]
        if pg_tags:
            author = work.get('author', 'Unknown')
            by_author[author].append({
                'id': work.get('id'),
                'title': work.get('title'),
                'pg_tags': sorted(pg_tags)
            })

    print('='*80)
    print('PATROLOGIA GRAECA VOLUME VERIFICATION')
    print('Comparing catalog tags against Roger Pearse\'s canonical index')
    print('='*80)
    print()

    verified = []
    mismatches = []
    unknown_authors = []
    anonymous_case = []

    for author in sorted(by_author.keys()):
        works = by_author[author]

        # Special case: Anonymous
        if author == 'Ἀνώνυμος':
            anonymous_case.append((author, works))
            continue

        # Get our volume tags
        all_pg_tags = set()
        for w in works:
            all_pg_tags.update(w['pg_tags'])

        our_volumes = set()
        for tag in all_pg_tags:
            our_volumes.update(parse_pg_tag(tag))

        # Look up canonical volumes
        author_key = AUTHOR_NORMALIZE.get(author)

        if author_key is None:
            unknown_authors.append((author, works, sorted(all_pg_tags)))
            continue

        canonical = canonical_volumes_for_author(author_key)

        if canonical is None:
            unknown_authors.append((author, works, sorted(all_pg_tags)))
            continue

        expected_volumes, note = canonical

        # Compare
        our_vol_set = set(str(v) for v in our_volumes)
        expected_vol_set = set(str(v) for v in expected_volumes)

        if our_vol_set == expected_vol_set:
            verified.append((author, len(works), sorted(all_pg_tags), note))
        else:
            missing = expected_vol_set - our_vol_set
            extra = our_vol_set - expected_vol_set
            mismatches.append((author, len(works), sorted(all_pg_tags),
                             expected_volumes, missing, extra, note))

    # Print verified authors
    print(f'✓ VERIFIED AUTHORS ({len(verified)}):')
    print('-'*80)
    for author, work_count, pg_tags, note in verified:
        print(f'{author}: {work_count} works => {", ".join(pg_tags)}')
        if note:
            print(f'  Note: {note}')
    print()

    # Print mismatches
    if mismatches:
        print(f'✗ MISMATCHES ({len(mismatches)}):')
        print('-'*80)
        for author, work_count, our_tags, expected, missing, extra, note in mismatches:
            print(f'\n{author}: {work_count} works')
            print(f'  Our tags: {", ".join(our_tags)}')
            print(f'  Expected: PG {", ".join(str(v) for v in expected)}')
            if note:
                print(f'  Note: {note}')
            if missing:
                print(f'  MISSING from our catalog: {", ".join(sorted(missing))}')
            if extra:
                print(f'  EXTRA in our catalog: {", ".join(sorted(extra))}')
        print()

    # Print unknown authors
    if unknown_authors:
        print(f'? UNKNOWN AUTHORS ({len(unknown_authors)}):')
        print('These authors are in our catalog but not in the canonical mapping.')
        print('-'*80)
        for author, works, pg_tags in unknown_authors:
            print(f'{author}: {len(works)} works => {", ".join(pg_tags)}')
        print()

    # Print anonymous case
    if anonymous_case:
        print('⚠ ANONYMOUS WORKS:')
        print('-'*80)
        for author, works in anonymous_case:
            for w in works:
                print(f'{w["id"]}: {w["title"][:60]}...')
                print(f'  Tags: {", ".join(w["pg_tags"])}')
                print(f'  Note: From catch-all folders; volume attribution uncertain')
        print()

    # Summary
    print('='*80)
    print('SUMMARY')
    print('='*80)
    print(f'Total authors with PG tags: {len(by_author)}')
    print(f'Verified (exact match): {len(verified)}')
    print(f'Mismatches (wrong/incomplete volumes): {len(mismatches)}')
    print(f'Unknown (not in canonical index): {len(unknown_authors)}')
    print(f'Anonymous (uncertain attribution): {len(anonymous_case)}')
    print()

    # Recommendations
    print('RECOMMENDATIONS:')
    print('-'*80)
    if mismatches:
        print('1. Review MISMATCHES carefully - these may indicate:')
        print('   - Incomplete imports (missing volumes)')
        print('   - Incorrect tagging by tag_filetags.py')
        print('   - Authors appearing in multiple PG volumes')
    if unknown_authors:
        print('2. UNKNOWN AUTHORS need canonical mapping entries in:')
        print('   - scripts/verify_pg_volumes.py (this script)')
        print('   - scripts/tag_filetags.py (if tagging is automated)')
    if anonymous_case:
        print('3. ANONYMOUS works need individual review:')
        print('   - Check PDF source paths in log/pg-migne-pdf-manifest.json')
        print('   - Manually verify correct PG volume from content')
        print('   - Update #+FILETAGS: in .org file if needed')


if __name__ == '__main__':
    main()
