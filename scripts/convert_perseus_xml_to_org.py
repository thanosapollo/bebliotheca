#!/usr/bin/env python3
"""Convert Perseus Digital Library TEI XML files to Org mode format.

Converts TEI XML files from canonical-greekLit and canonical-latinLit into
Org-mode format with language-appropriate heading labels.

Source XML data lives in git submodules. Use the unified import pipeline:

    python3 scripts/import_sources.py perseus-greek
    python3 scripts/import_sources.py perseus-latin

Reads TEI XML files under data/*/*, detects language from TEI headers
(Greek, Latin, or English), and outputs .org files into gr/, la/, and en/
subdirectories (relative to CWD). Filenames use English titles with
double-dash author separator: title--author.org

Handles poetry, prose, and drama. Structural divisions (book, chapter,
section) become Org headings with CUSTOM_IDs for cross-language linking.
"""

import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

# TEI namespace
TEI_NS = {'tei': 'http://www.tei-c.org/ns/1.0'}

# Common Greek to English transliterations for slugs
GREEK_SLUG_MAP = {
    'Εἰδύλλια': 'idylls',
    'Θεόκριτος': 'theocritus',
    'Πλάτων': 'plato',
    'Ὀδύσσεια': 'odyssey',
    'Ἰλιάς': 'iliad',
    'Πολιτεία': 'republic',
}


def make_slug(text: str) -> str:
    """Convert text to lowercase slug format."""
    text = GREEK_SLUG_MAP.get(text, text)
    # Remove punctuation
    text = re.sub(r'[,;:()\[\]\'""\u201c\u201d\u2018\u2019\u00ab\u00bb.!?]', '', text)
    # Remove non-ASCII/non-word characters
    text = re.sub(r'[^\x00-\x7F\w\s-]+', '', text)
    text = text.lower().strip()
    text = re.sub(r'[-\s]+', '-', text)
    return text


def clean_whitespace(text: str) -> str:
    """Clean up excessive whitespace: strip lines, collapse blank runs."""
    lines = [line.strip() for line in text.split('\n')]
    result: List[str] = []
    prev_blank = False
    for line in lines:
        if line == '':
            if not prev_blank:
                result.append(line)
            prev_blank = True
        else:
            result.append(line)
            prev_blank = False
    return '\n'.join(result)


def add_custom_ids(org_text: str) -> str:
    """Add positional hN-hN CUSTOM_IDs to every Org heading.

    Mirrors thanos/org-add-custom-ids: each heading gets a hierarchical
    ID based on its position among siblings at each depth level.
    Replaces any existing CUSTOM_ID in PROPERTIES drawers.
    """
    lines = org_text.split('\n')
    result: List[str] = []
    counters: Dict[int, int] = {}
    i = 0

    while i < len(lines):
        line = lines[i]
        m = re.match(r'^(\*+)\s', line)

        if m:
            depth = len(m.group(1))
            counters[depth] = counters.get(depth, 0) + 1
            for d in list(counters):
                if d > depth:
                    del counters[d]
            custom_id = '-'.join(
                f'h{counters[d]}' for d in sorted(counters) if d <= depth
            )

            result.append(line)
            i += 1

            # Check for existing PROPERTIES drawer
            if i < len(lines) and lines[i].strip() == ':PROPERTIES:':
                i += 1  # skip :PROPERTIES:
                other_props: List[str] = []
                while i < len(lines) and lines[i].strip() != ':END:':
                    if ':CUSTOM_ID:' not in lines[i]:
                        other_props.append(lines[i])
                    i += 1
                i += 1  # skip :END:
                result.append(':PROPERTIES:')
                result.append(f':CUSTOM_ID: {custom_id}')
                result.extend(other_props)
                result.append(':END:')
            else:
                # Insert new PROPERTIES drawer
                result.append(':PROPERTIES:')
                result.append(f':CUSTOM_ID: {custom_id}')
                result.append(':END:')
        else:
            result.append(line)
            i += 1

    return '\n'.join(result)


def get_text_content(elem: ET.Element, preserve_children: bool = False) -> str:
    """Get text content of a TEI element, optionally processing children."""
    if preserve_children:
        parts: List[str] = []
        if elem.text:
            parts.append(elem.text)
        for child in elem:
            tag = child.tag.replace('{' + TEI_NS['tei'] + '}', '')
            if tag in ['quote', 'q']:
                parts.append('/')
                parts.append(get_text_content(child, True))
                parts.append('/')
            elif tag not in ['note', 'bibl']:
                parts.append(get_text_content(child, True))
            if child.tail:
                parts.append(child.tail)
        return ''.join(parts)
    else:
        return ''.join(elem.itertext())


class TEIToOrgConverter:
    """Convert TEI XML to Org mode format."""

    # Subtypes that create structural heading levels
    STRUCTURAL_SUBTYPES = {
        'book': 'bk', 'Book': 'bk',
        'chapter': 'ch',
        'section': 'sec',
        'subsection': 'subsec',
        'subchapter': 'subch',
    }

    # Heading labels by language
    HEADING_LABELS_EN = {
        'book': 'Book', 'Book': 'Book', 'chapter': 'Chapter',
        'section': 'Section', 'subsection': 'Subsection',
        'subchapter': 'Subchapter',
    }
    HEADING_LABELS_GR = {
        'book': 'Βιβλίον', 'Book': 'Βιβλίον', 'chapter': 'Κεφάλαιον',
        'section': 'Τμῆμα', 'subsection': 'Ὑποτμῆμα',
        'subchapter': 'Ὑποκεφάλαιον',
    }
    HEADING_LABELS_LA = {
        'book': 'Liber', 'Book': 'Liber', 'chapter': 'Caput',
        'section': 'Sectio', 'subsection': 'Subsectio',
        'subchapter': 'Subcaput',
    }

    # Preamble n-values: these intro/preface sections use extra heading depth
    # instead of pushing to structural_path (children stay at grandparent level)
    PREAMBLE_N_VALUES = frozenset([
        'intro', 'pr', 'pref', 'praef', 'sal', 'prologue',
        'front', 'back', 'appendix', 'app', 'argument', 'arg', '0',
    ])

    # Normalize n-values across editions for consistent IDs
    N_VALUE_NORMALIZE = {
        'argument': 'arg',
        'pref': 'praef',
    }

    # HTML/XML entities commonly found in Perseus TEI files.
    # Python's ElementTree only knows &amp; &lt; &gt; &apos; &quot; -
    # everything else must be declared or replaced before parsing.
    HTML_ENTITIES = {
        '&mdash;': '\u2014', '&ndash;': '\u2013',
        '&lsquo;': '\u2018', '&rsquo;': '\u2019',
        '&ldquo;': '\u201c', '&rdquo;': '\u201d',
        '&dagger;': '\u2020', '&Dagger;': '\u2021',
        '&hellip;': '\u2026', '&bull;': '\u2022',
        '&prime;': '\u2032', '&Prime;': '\u2033',
        '&trade;': '\u2122', '&copy;': '\u00a9',
        '&reg;': '\u00ae', '&deg;': '\u00b0',
        '&plusmn;': '\u00b1', '&times;': '\u00d7',
        '&divide;': '\u00f7', '&micro;': '\u00b5',
        '&sect;': '\u00a7', '&para;': '\u00b6',
        '&middot;': '\u00b7', '&cedil;': '\u00b8',
        '&nbsp;': ' ',
        # Latin-1 accented characters used in Perseus Latin files
        '&Agrave;': '\u00c0', '&Aacute;': '\u00c1', '&Acirc;': '\u00c2',
        '&Atilde;': '\u00c3', '&Auml;': '\u00c4', '&Aring;': '\u00c5',
        '&AElig;': '\u00c6', '&Ccedil;': '\u00c7',
        '&Egrave;': '\u00c8', '&Eacute;': '\u00c9', '&Ecirc;': '\u00ca',
        '&Euml;': '\u00cb',
        '&Igrave;': '\u00cc', '&Iacute;': '\u00cd', '&Icirc;': '\u00ce',
        '&Iuml;': '\u00cf',
        '&ETH;': '\u00d0', '&Ntilde;': '\u00d1',
        '&Ograve;': '\u00d2', '&Oacute;': '\u00d3', '&Ocirc;': '\u00d4',
        '&Otilde;': '\u00d5', '&Ouml;': '\u00d6',
        '&Ugrave;': '\u00d9', '&Uacute;': '\u00da', '&Ucirc;': '\u00db',
        '&Uuml;': '\u00dc', '&Yacute;': '\u00dd',
        '&THORN;': '\u00de', '&szlig;': '\u00df',
        '&agrave;': '\u00e0', '&aacute;': '\u00e1', '&acirc;': '\u00e2',
        '&atilde;': '\u00e3', '&auml;': '\u00e4', '&aring;': '\u00e5',
        '&aelig;': '\u00e6', '&ccedil;': '\u00e7',
        '&egrave;': '\u00e8', '&eacute;': '\u00e9', '&ecirc;': '\u00ea',
        '&euml;': '\u00eb',
        '&igrave;': '\u00ec', '&iacute;': '\u00ed', '&icirc;': '\u00ee',
        '&iuml;': '\u00ef',
        '&eth;': '\u00f0', '&ntilde;': '\u00f1',
        '&ograve;': '\u00f2', '&oacute;': '\u00f3', '&ocirc;': '\u00f4',
        '&otilde;': '\u00f5', '&ouml;': '\u00f6',
        '&ugrave;': '\u00f9', '&uacute;': '\u00fa', '&ucirc;': '\u00fb',
        '&uuml;': '\u00fc', '&yacute;': '\u00fd',
        '&thorn;': '\u00fe', '&yuml;': '\u00ff',
    }

    # Regex matching any &word; entity that isn't one of the 5 XML built-ins
    _ENTITY_RE = re.compile(r'&(?!amp;|lt;|gt;|apos;|quot;)([A-Za-z][A-Za-z0-9.]*);')

    @classmethod
    def _resolve_entities(cls, xml_text):
        """Replace HTML entities with Unicode characters, drop unknown ones."""
        def _replace(m):
            entity = m.group(0)
            return cls.HTML_ENTITIES.get(entity, '')
        return cls._ENTITY_RE.sub(_replace, xml_text)

    def __init__(self, xml_file):
        self.xml_file = xml_file
        # Pre-process to resolve HTML entities before XML parsing
        with open(xml_file, 'r', encoding='utf-8') as f:
            xml_text = f.read()
        xml_text = self._resolve_entities(xml_text)
        self.root = ET.fromstring(xml_text)
        self.output: List[str] = []
        self.structural_path: List[int] = []
        self.current_card: Optional[str] = None
        self.in_preamble = False
        self.language = 'en'
        self._metadata: Dict[str, str] = {}

    def get_english_title_from_pair(self):
        """Try to get English title from corresponding English file."""
        if 'grc' in self.xml_file or 'gre' in self.xml_file:
            eng_file = self.xml_file.replace('-grc', '-eng')
        elif 'lat' in self.xml_file:
            eng_file = self.xml_file.replace('-lat', '-eng')
        else:
            return None

        # Try different English file variants
        for variant in [eng_file,
                       eng_file.replace('eng2', 'eng1'),
                       eng_file.replace('eng2', 'eng3'),
                       eng_file.replace('eng2', 'eng4'),
                       eng_file.replace('eng2', 'eng5'),
                       eng_file.replace('eng2', 'eng6')]:
            if os.path.exists(variant):
                try:
                    tree = ET.parse(variant)
                    root = tree.getroot()
                    title = root.find('.//tei:titleStmt/tei:title', TEI_NS)
                    if title is not None and title.text:
                        return title.text.strip()
                except Exception:
                    continue
        return None

    def get_metadata(self):
        """Extract metadata from TEI header."""
        metadata = {}

        # Detect language - prefer filename over TEI metadata
        filename = os.path.basename(self.xml_file)
        if any(lang in filename for lang in ['grc', 'gre']):
            metadata['language'] = 'gr'
        elif 'lat' in filename:
            metadata['language'] = 'la'
        elif 'eng' in filename:
            metadata['language'] = 'en'
        else:
            # Fallback to TEI header metadata
            lang_elem = self.root.find('.//tei:profileDesc/tei:langUsage/tei:language', TEI_NS)
            if lang_elem is not None:
                lang_ident = lang_elem.get('ident', 'eng')
                if lang_ident in ['grc', 'gre', 'gr', 'greek']:
                    metadata['language'] = 'gr'
                elif lang_ident in ['lat', 'la', 'latin']:
                    metadata['language'] = 'la'
                elif lang_ident in ['eng', 'en', 'english']:
                    metadata['language'] = 'en'
                else:
                    metadata['language'] = 'en'
            else:
                # Last resort: xml:lang attribute
                text_elem = self.root.find('.//tei:text', TEI_NS)
                if text_elem is not None:
                    lang = text_elem.get('{http://www.w3.org/XML/1998/namespace}lang', 'eng')
                    metadata['language'] = 'gr' if lang in ['grc', 'gre'] else 'la' if lang in ['lat'] else 'en'
                else:
                    metadata['language'] = 'en'

        # Get both language versions of title
        titles = self.root.findall('.//tei:titleStmt/tei:title', TEI_NS)
        title_text = None
        english_title = None

        # Get language-appropriate title for #+TITLE header
        if metadata['language'] == 'gr':
            # For Greek files, prefer Greek title
            for title_elem in titles:
                lang = title_elem.get('{http://www.w3.org/XML/1998/namespace}lang', '')
                if lang in ['grc', 'gre', 'gr'] and title_elem.text:
                    title_text = title_elem.text.strip()
                    break
        elif metadata['language'] == 'la':
            # For Latin files, prefer Latin title
            for title_elem in titles:
                lang = title_elem.get('{http://www.w3.org/XML/1998/namespace}lang', '')
                if lang in ['lat', 'la'] and title_elem.text:
                    title_text = title_elem.text.strip()
                    break
        else:
            # For English files, prefer English title
            for title_elem in titles:
                lang = title_elem.get('{http://www.w3.org/XML/1998/namespace}lang', '')
                if lang in ['eng', 'en', ''] and title_elem.text:  # Empty lang often means English
                    title_text = title_elem.text.strip()
                    break

        # Get English title for filename (always)
        for title_elem in titles:
            lang = title_elem.get('{http://www.w3.org/XML/1998/namespace}lang', '')
            if lang in ['eng', 'en', ''] and title_elem.text:
                english_title = title_elem.text.strip()
                break

        # If no language-specific title found, use the first title
        if not title_text and titles:
            title_text = titles[0].text.strip() if titles[0].text else None

        # If no English title found, try to get from English counterpart file
        if not english_title:
            english_title = self.get_english_title_from_pair()

        # If still no English title, use the title we have
        if not english_title:
            english_title = title_text

        if title_text:
            metadata['title'] = title_text
        if english_title:
            metadata['english_title'] = english_title

        # Author
        author = self.root.find('.//tei:titleStmt/tei:author', TEI_NS)
        if author is not None and author.text:
            metadata['author'] = author.text.strip()

        # Editor/Translator
        editor = self.root.find('.//tei:titleStmt/tei:editor', TEI_NS)
        if editor is not None and editor.text:
            role = editor.get('role', 'editor')
            metadata[role] = editor.text.strip()

        # Publisher
        publisher = self.root.find('.//tei:publicationStmt/tei:publisher', TEI_NS)
        if publisher is not None and publisher.text:
            metadata['publisher'] = publisher.text.strip()

        return metadata

    def _heading_stars(self, extra=0):
        """Return Org heading stars based on current structural depth.

        Depth 1 = *, depth 2 = **, etc.  Capped at **** (level 4).
        `extra` adds additional levels (e.g. +1 for cards, +2 for speakers).
        """
        depth = len(self.structural_path) + extra
        return '*' * max(1, min(depth, 4))

    def _process_children(self, elem, result, level, in_quote, in_poetry):
        """Process an element's text and children into result list."""
        if elem.text:
            result.append(elem.text)
        for child in elem:
            result.append(self.process_element(child, level + 1, in_quote=in_quote, in_poetry=in_poetry))
            if child.tail:
                result.append(child.tail)

    def process_element(self, elem, level=0, in_quote=False, in_poetry=False):
        """Recursively process XML elements and convert to Org format."""
        tag = elem.tag.replace('{' + TEI_NS['tei'] + '}', '')

        # Skip these elements entirely (including their content)
        if tag in ['note', 'bibl', 'teiHeader', 'title', 'pb']:
            return ''

        result = []

        # Handle structural elements
        if tag == 'div':
            div_type = elem.get('type', '')
            subtype = elem.get('subtype', '')
            n = elem.get('n', '')

            # Skip the top-level edition/translation div with URN
            if div_type in ('edition', 'translation') and 'urn:cts' in (n or ''):
                self._process_children(elem, result, level, in_quote, in_poetry)
                return ''.join(result)

            # Check if this is a structural subtype that gets a CUSTOM_ID
            abbrev = self.STRUCTURAL_SUBTYPES.get(subtype)

            if abbrev and n:
                # Normalize n-value for cross-edition consistency
                n_normalized = self.N_VALUE_NORMALIZE.get(n, n)
                # Skip CUSTOM_ID for preamble sections (intro, arg, etc.)
                is_preamble = n_normalized in self.PREAMBLE_N_VALUES

                if is_preamble or self.in_preamble:
                    # Preamble: heading with extra depth level,
                    # don't push to path (children inherit grandparent context)
                    stars = self._heading_stars(extra=1)
                    labels = (self.HEADING_LABELS_GR if self.language == 'gr'
                              else self.HEADING_LABELS_LA if self.language == 'la'
                              else self.HEADING_LABELS_EN)
                    label = labels.get(subtype, subtype.title())
                    result.append(f"\n{stars} {label} {n}\n")
                    old_preamble = self.in_preamble
                    self.in_preamble = True
                    self._process_children(elem, result, level, in_quote, in_poetry)
                    self.in_preamble = old_preamble
                else:
                    # Structural div: push depth, process children, pop
                    self.structural_path.append(0)
                    self.current_card = None
                    stars = self._heading_stars()
                    labels = (self.HEADING_LABELS_GR if self.language == 'gr'
                              else self.HEADING_LABELS_LA if self.language == 'la'
                              else self.HEADING_LABELS_EN)
                    label = labels.get(subtype, subtype.title())
                    result.append(f"\n{stars} {label} {n}\n")

                    self._process_children(elem, result, level, in_quote, in_poetry)
                    self.structural_path.pop()
                return ''.join(result)

            elif subtype == 'card' and n:
                # Card div: heading, track card for depth calculation
                self.current_card = n
                stars = self._heading_stars(extra=1)
                result.append(f"\n{stars} {n}\n")
                self._process_children(elem, result, level, in_quote, in_poetry)
                return ''.join(result)

            elif subtype == 'verse':
                # Verses should be inline, not headings
                if n:
                    result.append(f"={n}= ")
                # Fall through to bottom for children

            elif subtype == 'poem':
                # For poems, don't add heading here - handled by head tag
                in_poetry = True
                # Fall through to bottom for children

            elif n and div_type not in ('edition', 'translation') and subtype != 'verse':
                # Non-structural div with n (e.g., strophe, antistrophe, episode)
                # Heading for readability, no CUSTOM_ID (these often differ between languages)
                stars = self._heading_stars(extra=1)
                result.append(f"\n{stars} {n}\n")
                # Fall through to bottom for children

        # Handle head tags (poem/section titles)
        elif tag == 'head':
            text = get_text_content(elem)
            if text:
                if not self.structural_path:
                    # Top-level head is redundant with #+TITLE: - skip it
                    pass
                else:
                    stars = self._heading_stars(extra=1)
                    result.append(f"\n{stars} {text}\n")
            return ''.join(result)

        # Handle sp (speech) tags - contains speaker + lines
        elif tag == 'sp':
            has_lg = elem.find('.//tei:lg', TEI_NS) is not None
            in_poetry = has_lg

        # Handle speaker tags (for drama and poetry dialogues)
        # No CUSTOM_ID: speaker names differ by language and card numbers
        # vary between editions, making cross-language IDs unreliable
        elif tag == 'speaker':
            text = get_text_content(elem)
            if text:
                # +2 if inside a card (card is +1), +1 if directly in structural context
                extra = 2 if self.current_card is not None else 1
                stars = self._heading_stars(extra=extra)
                result.append(f"\n{stars} {text}\n\n")
            return ''.join(result)

        # Handle label tags (alternative speaker markers in dialogues)
        elif tag == 'label':
            text = get_text_content(elem)
            if text:
                extra = 2 if self.current_card is not None else 1
                stars = self._heading_stars(extra=extra)
                result.append(f"\n{stars} {text}\n\n")
            return ''.join(result)

        # Handle said tags (dialogue attribution)
        elif tag == 'said':
            who = elem.get('who', '').replace('#', '')
            merge = elem.get('rend') == 'merge'
            if who:
                if not merge:
                    if level == 0:
                        extra = 2 if self.current_card is not None else 1
                        stars = self._heading_stars(extra=extra)
                        result.append(f"\n{stars} {who}\n")

        # Handle lg (line group) tags - poetry line group
        elif tag == 'lg':
            lines = []
            for line_elem in elem.findall('.//tei:l', TEI_NS):
                line_text = get_text_content(line_elem, preserve_children=True).strip()
                if line_text:
                    lines.append(f"        {line_text}")
            if lines:
                result.append('\n'.join(lines) + '\n')
            return ''.join(result)

        # Handle line tags (poetry) - skip if handled by lg
        elif tag == 'l':
            pass

        # Handle paragraph tags
        elif tag == 'p':
            pass

        # Handle quotes - preserve nested structure
        elif tag in ['quote', 'q']:
            qtype = elem.get('type', '')
            if qtype in ['spoken', 'emph']:
                if elem.text:
                    result.append(elem.text)
                for child in elem:
                    result.append(self.process_element(child, level + 1, in_quote=True))
                    if child.tail:
                        result.append(child.tail)
                return ''.join(result)
            else:
                text = get_text_content(elem)
                result.append(f"/{text}/")
                return ''.join(result)

        # Handle milestones
        elif tag == 'milestone':
            unit = elem.get('unit', '')
            n = elem.get('n', '')
            resp = elem.get('resp', '')
            ed = elem.get('ed', '')

            if resp == 'Stephanus' and n:
                result.append(f" [{n}] ")
            elif ed == 'P' and unit == 'para':
                result.append("\n\n")
            elif unit == 'para' or unit == 'Para':
                result.append("\n\n")
            elif unit == 'card' and n:
                # Track card for depth calculation
                self.current_card = n
                stars = self._heading_stars(extra=1)
                result.append(f"\n{stars} {n}\n")

        # Handle placeName, persName, etc. - just keep the text
        elif tag in ['placeName', 'persName', 'name', 'foreign', 'gloss']:
            text = get_text_content(elem)
            result.append(text)
            return ''.join(result)

        # Handle cit - just process children
        elif tag == 'cit':
            pass

        # Handle gap (missing text)
        elif tag == 'gap':
            reason = elem.get('reason', '')
            result.append(f" [{reason}] ")
            return ''.join(result)

        # Add element's direct text
        if elem.text:
            result.append(elem.text)

        # Process children
        for child in elem:
            result.append(self.process_element(child, level + 1, in_quote=in_quote, in_poetry=in_poetry))
            if child.tail:
                result.append(child.tail)

        # Add paragraph break after paragraphs
        if tag == 'p':
            result.append('\n\n')

        return ''.join(result)

    def detect_content_language(self):
        """Detect actual language from XML body text using script analysis.

        Returns 'gr' if the body is predominantly Greek script, 'en' if
        predominantly Latin script, or None if indeterminate.  This overrides
        incorrect language metadata in some Perseus TEI files.
        """
        body = self.root.find('.//tei:text/tei:body', TEI_NS)
        if body is None:
            return None

        text = ''.join(body.itertext())

        greek_count = 0
        latin_count = 0
        for c in text:
            cp = ord(c)
            if (0x0370 <= cp <= 0x03FF) or (0x1F00 <= cp <= 0x1FFF):
                greek_count += 1
            elif (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A) or (0x00C0 <= cp <= 0x024F):
                latin_count += 1

        total = greek_count + latin_count
        if total == 0:
            return None

        if greek_count / total > 0.7:
            return 'gr'
        elif latin_count / total > 0.7:
            return 'en'
        return None

    def convert(self):
        """Convert the XML file to Org format."""
        # Extract metadata (cached for reuse by save())
        metadata = self.get_metadata()
        self._metadata = metadata

        title = metadata.get('title', 'Untitled')
        author = metadata.get('author', 'Unknown')
        lang = metadata.get('language', 'en')

        # Override language if content script disagrees with XML metadata.
        # Content detection distinguishes Greek script from Latin script but
        # cannot distinguish Latin language from English (both use Latin script).
        # Only override when Greek script is involved in the mismatch.
        detected = self.detect_content_language()
        if detected and detected != lang and (detected == 'gr' or lang == 'gr'):
            lang = detected
            metadata['language'] = lang

        self.language = lang
        lang_code = 'el' if lang == 'gr' else lang  # 'la' or 'en' pass through

        # Generate filename for EXPORT_FILE_NAME (always use English title)
        english_title = metadata.get('english_title') or title
        title_slug = make_slug(english_title)
        author_slug = make_slug(author)
        export_filename = f"{title_slug}--{author_slug}"

        # Add Org mode headers
        self.output.append(f"#+TITLE: {title}\n")
        self.output.append(f"#+AUTHOR: {author}\n")
        self.output.append("#+SETUPFILE: ../../public/themes/org/theme-readtheorg-local.setup\n")
        self.output.append("#+OPTIONS: ^:t num:nil html-style:nil date:nil html-postamble:nil\n")
        self.output.append("#+startup: overview\n")
        self.output.append(f"#+EXPORT_FILE_NAME: ../../public/{lang}/{export_filename}\n")
        if lang_code != 'en':
            self.output.append(f"#+LANGUAGE: {lang_code}\n")
        self.output.append("\n")

        # Add translator/editor info in quote block if available
        editor = metadata.get('editor') or metadata.get('translator')
        if editor:
            self.output.append("#+BEGIN_QUOTE\n")
            role = 'translated' if 'translator' in metadata else 'edited'
            self.output.append(f"{title} {role} by {editor}\n")
            self.output.append("#+END_QUOTE\n\n")

        # Process the body
        body = self.root.find('.//tei:text/tei:body', TEI_NS)
        if body is not None:
            content = self.process_element(body)
            self.output.append(content)

        # Join and clean up the output
        result = ''.join(self.output)
        result = clean_whitespace(result)

        # Post-process: add positional CUSTOM_IDs to every heading
        result = add_custom_ids(result)

        return result

    def save(self, output_file=None):
        """Convert and save to an .org file."""
        # convert() applies content-based language detection, sets self.language,
        # and caches metadata in self._metadata
        content = self.convert()

        if output_file is None:
            metadata = self._metadata
            title = metadata.get('english_title') or metadata.get('title', 'untitled')
            author = metadata.get('author', 'unknown')

            filename = f"{make_slug(title)}--{make_slug(author)}.org"

            lang_dir = Path(self.language)
            lang_dir.mkdir(exist_ok=True)
            output_file = lang_dir / filename

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)

        return output_file


def process_directory(data_dir='data', pattern='*.xml'):
    """Process XML files grouped by work to ensure consistent naming.

    Groups TEI files by work directory (parent dir), detects the original
    language (Greek or Latin), converts originals first, then English
    translations using the original's filename stem. Works without an
    original-language file are skipped.
    """
    data_path = Path(data_dir)

    if not data_path.exists():
        print(f"Error: Directory '{data_dir}' not found")
        return

    # Find all XML files
    xml_files = list(data_path.rglob(pattern))
    xml_files = [f for f in xml_files if f.name != '__cts__.xml']
    xml_files = [f for f in xml_files
                 if any(lang in f.name for lang in ['grc', 'gre', 'lat', 'eng'])]

    print(f"Found {len(xml_files)} XML files to convert")

    # Group by work directory
    works = {}
    for xml_file in xml_files:
        work_dir = str(xml_file.parent)
        if work_dir not in works:
            works[work_dir] = {'grc': [], 'lat': [], 'eng': []}
        if any(lang in xml_file.name for lang in ['grc', 'gre']):
            works[work_dir]['grc'].append(xml_file)
        elif 'lat' in xml_file.name:
            works[work_dir]['lat'].append(xml_file)
        elif 'eng' in xml_file.name:
            works[work_dir]['eng'].append(xml_file)

    converted = 0
    skipped = 0
    errors = 0

    for work_dir in sorted(works):
        grc_files = sorted(works[work_dir]['grc'])
        lat_files = sorted(works[work_dir]['lat'])
        eng_files = sorted(works[work_dir]['eng'])

        # Determine original: Greek takes priority, then Latin
        if grc_files:
            orig_files = grc_files
            orig_expected_lang = 'gr'
        elif lat_files:
            orig_files = lat_files
            orig_expected_lang = 'la'
        else:
            # No original - skip English-only works
            for f in eng_files:
                print(f"Skipping (no original): {f}")
            skipped += len(eng_files)
            continue

        # Convert original file (prefer highest version number - last after sort)
        orig_file = orig_files[-1]
        try:
            print(f"Converting: {orig_file}")
            converter = TEIToOrgConverter(str(orig_file))
            orig_output = converter.save()

            if converter.language != orig_expected_lang:
                print(f"  Skipping work (content is {converter.language}, not {orig_expected_lang})")
                os.remove(orig_output)
                skipped += 1 + len(eng_files)
                continue

            orig_stem = Path(orig_output).stem
            print(f"  => {orig_output}")
            converted += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            errors += 1
            continue

        if eng_files:
            # Convert best English file (highest version) using original's filename
            eng_file = eng_files[-1]
            try:
                print(f"Converting: {eng_file}")
                converter = TEIToOrgConverter(str(eng_file))
                content = converter.convert()

                if converter.language != 'en':
                    print(f"  Skipping translation (content is {converter.language}, not English)")
                    skipped += 1
                    continue

                # Override #+EXPORT_FILE_NAME: to match original file's stem
                content = re.sub(
                    r'#\+EXPORT_FILE_NAME: ../../public/\w+/\S+',
                    f'#+EXPORT_FILE_NAME: ../../public/en/{orig_stem}',
                    content
                )

                output_file = Path('en') / f'{orig_stem}.org'
                Path('en').mkdir(exist_ok=True)
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  => {output_file}")
                converted += 1
            except Exception as e:
                print(f"  ERROR: {e}")
                errors += 1

    print(f"\nConversion complete!")
    print(f"Successfully converted: {converted}")
    print(f"Skipped (no original): {skipped}")
    print(f"Errors: {errors}")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        # Single file mode
        xml_file = sys.argv[1]
        if not Path(xml_file).exists():
            print(f"Error: File '{xml_file}' not found")
            sys.exit(1)

        converter = TEIToOrgConverter(xml_file)
        output_file = converter.save()
        print(f"Converted: {xml_file} => {output_file}")
    else:
        # Batch mode - process all files
        process_directory()


if __name__ == '__main__':
    main()
