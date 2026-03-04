#!/usr/bin/env python3
"""
Validate heading structure consistency across translation pairs.

Scans content/gr/, content/en/, and content/la/ directories for .org files,
extracts heading structures and CUSTOM_IDs, and compares paired translations
to ensure structural alignment for cross-language linking.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class HeadingNode:
    """A single heading extracted from an Org-mode file."""
    line_number: int
    level: int
    text: str
    custom_id: Optional[str] = None


@dataclass
class FileStructure:
    """Parsed structure of an Org-mode file."""
    file_path: Path
    language: str
    title: str
    author: str
    headings: List[HeadingNode] = field(default_factory=list)
    pattern: str = "none"  # h0-flat, h1-hierarchical, flat-sequential, none


@dataclass
class ComparisonResult:
    """Result of comparing two translation files."""
    stem: str
    lang_a: str
    lang_b: str
    ids_only_in_a: List[str] = field(default_factory=list)
    ids_only_in_b: List[str] = field(default_factory=list)
    common_ids: List[str] = field(default_factory=list)
    order_match: bool = True
    pattern_a: str = "none"
    pattern_b: str = "none"
    severity: str = "info"  # error, warning, info


def parse_headings(file_path: Path) -> FileStructure:
    """
    Parse an Org-mode file and extract headings with CUSTOM_IDs.

    Args:
        file_path: Path to the .org file

    Returns:
        FileStructure with parsed headings and metadata
    """
    title = ""
    author = ""
    language = ""
    headings: List[HeadingNode] = []

    # Determine language from directory
    path_str = str(file_path)
    if "/en/" in path_str:
        language = "en"
    elif "/gr/" in path_str:
        language = "gr"
    elif "/la/" in path_str:
        language = "la"

    heading_re = re.compile(r"^(\*+)\s+(.+)$")
    custom_id_re = re.compile(r"^:CUSTOM_ID:\s+(.+)$")

    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    current_heading: Optional[HeadingNode] = None
    in_properties = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        # Parse header metadata (top of file)
        if stripped.startswith("#+TITLE:") or stripped.startswith("#+title:"):
            title = stripped.split(":", 1)[1].strip()
            continue
        if stripped.startswith("#+AUTHOR:") or stripped.startswith("#+author:"):
            author = stripped.split(":", 1)[1].strip()
            continue
        if stripped.startswith("#+LANGUAGE:") or stripped.startswith("#+language:"):
            lang = stripped.split(":", 1)[1].strip()
            if lang == "el":
                language = "gr"
            else:
                language = lang
            continue

        # Match headings
        m = heading_re.match(stripped)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            current_heading = HeadingNode(
                line_number=i,
                level=level,
                text=text,
            )
            headings.append(current_heading)
            in_properties = False
            continue

        # Track PROPERTIES drawers
        if stripped == ":PROPERTIES:":
            in_properties = True
            continue
        if stripped == ":END:":
            in_properties = False
            continue

        # Extract CUSTOM_ID from within PROPERTIES
        if in_properties and current_heading is not None:
            m_id = custom_id_re.match(stripped)
            if m_id:
                current_heading.custom_id = m_id.group(1).strip()

    structure = FileStructure(
        file_path=file_path,
        language=language,
        title=title,
        author=author,
        headings=headings,
    )
    structure.pattern = classify_pattern(headings)
    return structure


def classify_pattern(headings: List[HeadingNode]) -> str:
    """
    Classify the CUSTOM_ID pattern used in a file.

    Patterns:
        h0-flat: IDs like h0-h1, h0-h2 (single top-level, flat children)
        h1-hierarchical: IDs like h1, h1-h1, h2, h2-h1 (nested book/chapter)
        flat-sequential: IDs like h1, h2, h3 (flat numbered, no nesting)
        none: No CUSTOM_IDs found

    Args:
        headings: List of HeadingNode objects

    Returns:
        Pattern classification string
    """
    ids = [h.custom_id for h in headings if h.custom_id]

    if not ids:
        return "none"

    has_h0 = any(cid.startswith("h0") for cid in ids)
    has_hierarchical = any("-" in cid for cid in ids)
    has_top_level = any(re.match(r"^h\d+$", cid) for cid in ids)

    if has_h0 and has_hierarchical:
        return "h0-flat"
    if has_top_level and has_hierarchical:
        return "h1-hierarchical"
    if has_top_level and not has_hierarchical:
        return "flat-sequential"

    # Fallback: if we have hierarchical IDs but no plain top-level
    if has_hierarchical:
        return "h0-flat"

    return "none"


def group_files_by_stem(content_dir: Path) -> Dict[str, Dict[str, FileStructure]]:
    """
    Scan content directories and group files by filename stem.

    Args:
        content_dir: Path to the content/ directory

    Returns:
        Dictionary mapping stem -> {language: FileStructure}
    """
    groups: Dict[str, Dict[str, FileStructure]] = {}

    for lang_dir in ["gr", "en", "la"]:
        lang_path = content_dir / lang_dir
        if not lang_path.exists():
            continue

        for org_file in sorted(lang_path.glob("*.org")):
            if org_file.name.startswith(".") or org_file.name.startswith("#"):
                continue
            if org_file.name == "index.org":
                continue

            stem = org_file.stem
            structure = parse_headings(org_file)

            if stem not in groups:
                groups[stem] = {}
            groups[stem][structure.language] = structure

    return groups


def compare_structures(a: FileStructure, b: FileStructure) -> ComparisonResult:
    """
    Compare the heading structures of two translation files.

    Args:
        a: First file structure
        b: Second file structure

    Returns:
        ComparisonResult with differences and severity
    """
    ids_a = [h.custom_id for h in a.headings if h.custom_id]
    ids_b = [h.custom_id for h in b.headings if h.custom_id]

    set_a = set(ids_a)
    set_b = set(ids_b)

    common = sorted(set_a & set_b)
    only_a = sorted(set_a - set_b)
    only_b = sorted(set_b - set_a)

    # Check ordering of common IDs
    order_a = [cid for cid in ids_a if cid in set_b]
    order_b = [cid for cid in ids_b if cid in set_a]
    order_match = order_a == order_b

    # Determine severity
    diff_count = len(only_a) + len(only_b)
    pattern_mismatch = (
        a.pattern != b.pattern
        and a.pattern != "none"
        and b.pattern != "none"
    )

    if pattern_mismatch and not common:
        # Completely incompatible structures (no shared IDs)
        severity = "error"
    elif pattern_mismatch:
        # Different nesting depth but shared top-level IDs (edition difference)
        severity = "warning"
    elif diff_count > 3 or not order_match:
        severity = "warning"
    else:
        severity = "info"

    return ComparisonResult(
        stem=a.file_path.stem,
        lang_a=a.language,
        lang_b=b.language,
        ids_only_in_a=only_a,
        ids_only_in_b=only_b,
        common_ids=common,
        order_match=order_match,
        pattern_a=a.pattern,
        pattern_b=b.pattern,
        severity=severity,
    )


def generate_report(
    groups: Dict[str, Dict[str, FileStructure]],
    min_severity: str = "info",
    file_filter: Optional[str] = None,
) -> Tuple[str, int, List[ComparisonResult]]:
    """
    Generate a human-readable report of structure comparisons.

    Args:
        groups: Grouped file structures by stem
        min_severity: Minimum severity to include (info, warning, error)
        file_filter: Optional stem to filter to a single pair

    Returns:
        Tuple of (report text, exit code, filtered results list)
    """
    severity_order = {"info": 0, "warning": 1, "error": 2}
    min_level = severity_order.get(min_severity, 0)

    results: List[ComparisonResult] = []
    single_lang_count = 0
    no_ids_count = 0
    perfect_count = 0

    stems = sorted(groups.keys())
    if file_filter:
        stems = [s for s in stems if s == file_filter]
        if not stems:
            return f"Error: No files found with stem '{file_filter}'\n", 1, []

    for stem in stems:
        langs = groups[stem]

        # Skip files with only one language version
        if len(langs) < 2:
            single_lang_count += 1
            continue

        # Compare each pair of languages
        lang_keys = sorted(langs.keys())
        for i in range(len(lang_keys)):
            for j in range(i + 1, len(lang_keys)):
                a = langs[lang_keys[i]]
                b = langs[lang_keys[j]]

                # Skip if neither has CUSTOM_IDs
                ids_a = [h.custom_id for h in a.headings if h.custom_id]
                ids_b = [h.custom_id for h in b.headings if h.custom_id]
                if not ids_a and not ids_b:
                    no_ids_count += 1
                    continue

                result = compare_structures(a, b)
                if not result.ids_only_in_a and not result.ids_only_in_b and result.order_match:
                    perfect_count += 1
                results.append(result)

    # Build report
    lines = []
    lines.append("=" * 60)
    lines.append("  Heading Structure Validation Report")
    lines.append("=" * 60)
    lines.append("")

    # Calculate detailed statistics
    total_works = len(groups)

    # Count by language availability
    greek_only = sum(1 for stem, langs in groups.items() if 'gr' in langs and len(langs) == 1)
    english_only = sum(1 for stem, langs in groups.items() if 'en' in langs and len(langs) == 1)
    latin_only = sum(1 for stem, langs in groups.items() if 'la' in langs and len(langs) == 1)

    greek_with_en = sum(1 for stem, langs in groups.items() if 'gr' in langs and 'en' in langs)
    greek_with_la = sum(1 for stem, langs in groups.items() if 'gr' in langs and 'la' in langs)
    all_three = sum(1 for stem, langs in groups.items() if len(langs) == 3)

    total_greek = sum(1 for stem, langs in groups.items() if 'gr' in langs)
    total_english = sum(1 for stem, langs in groups.items() if 'en' in langs)
    total_latin = sum(1 for stem, langs in groups.items() if 'la' in langs)

    greek_no_translation = sum(1 for stem, langs in groups.items() if 'gr' in langs and len(langs) == 1)

    # Summary statistics
    lines.append(f"CORPUS STATISTICS:")
    lines.append(f"  Total unique works:       {total_works}")
    lines.append(f"  Greek texts:              {total_greek}")
    lines.append(f"  English translations:     {total_english}")
    lines.append(f"  Latin texts:              {total_latin}")
    lines.append("")
    lines.append(f"TRANSLATION COVERAGE:")
    lines.append(f"  Greek with English:       {greek_with_en} ({greek_with_en*100//total_greek if total_greek else 0}%)")
    lines.append(f"  Greek with Latin:         {greek_with_la} ({greek_with_la*100//total_greek if total_greek else 0}%)")
    lines.append(f"  All three languages:      {all_three}")
    lines.append(f"  Greek without translation:{greek_no_translation} ({greek_no_translation*100//total_greek if total_greek else 0}%)")
    lines.append(f"  English-only works:       {english_only}")
    lines.append(f"  Latin-only works:         {latin_only}")
    lines.append("")

    # Comparison statistics
    total_pairs = len(results)
    errors = [r for r in results if r.severity == "error"]
    warnings = [r for r in results if r.severity == "warning"]
    infos = [r for r in results if r.severity == "info" and (r.ids_only_in_a or r.ids_only_in_b or not r.order_match)]

    lines.append(f"STRUCTURE COMPARISON:")
    lines.append(f"  Total pairs compared:     {total_pairs}")
    lines.append(f"  Perfect matches:          {perfect_count} ({perfect_count*100//total_pairs if total_pairs else 0}%)")
    lines.append(f"  No CUSTOM_IDs (both):     {no_ids_count}")
    lines.append(f"  Errors (pattern mismatch):{len(errors)}")
    lines.append(f"  Warnings (>3 diff/order): {len(warnings)}")
    lines.append(f"  Info (1-3 differences):   {len(infos)}")
    lines.append("")

    # Filter and sort results by severity (errors first)
    filtered = [r for r in results if severity_order.get(r.severity, 0) >= min_level]
    filtered = [r for r in filtered if r.ids_only_in_a or r.ids_only_in_b or not r.order_match]
    filtered.sort(key=lambda r: -severity_order.get(r.severity, 0))

    if not filtered:
        lines.append("All checked pairs are consistent.")
        lines.append("")
    else:
        for r in filtered:
            severity_label = r.severity.upper()
            lines.append(f"[{severity_label}] {r.stem} ({r.lang_a} vs {r.lang_b})")
            lines.append(f"  Pattern: {r.pattern_a} vs {r.pattern_b}")
            lines.append(f"  Common IDs: {len(r.common_ids)}")

            if r.ids_only_in_a:
                lines.append(f"  Only in {r.lang_a} ({len(r.ids_only_in_a)}): {', '.join(r.ids_only_in_a[:10])}")
                if len(r.ids_only_in_a) > 10:
                    lines.append(f"    ... and {len(r.ids_only_in_a) - 10} more")

            if r.ids_only_in_b:
                lines.append(f"  Only in {r.lang_b} ({len(r.ids_only_in_b)}): {', '.join(r.ids_only_in_b[:10])}")
                if len(r.ids_only_in_b) > 10:
                    lines.append(f"    ... and {len(r.ids_only_in_b) - 10} more")

            if not r.order_match:
                lines.append("  Order: MISMATCH (common IDs appear in different order)")
            lines.append("")

    report = "\n".join(lines)

    # Exit code: fail if any results at or above min_severity have issues
    has_failures = len(filtered) > 0
    return report, 1 if has_failures else 0, filtered


def generate_json(
    groups: Dict[str, Dict[str, FileStructure]],
    output_path: Path,
) -> None:
    """
    Export structure data as JSON.

    Args:
        groups: Grouped file structures by stem
        output_path: Path to write the JSON file
    """
    data = {}

    for stem in sorted(groups.keys()):
        langs = groups[stem]
        work = {}

        for lang, structure in sorted(langs.items()):
            headings = []
            for h in structure.headings:
                entry = {
                    "line": h.line_number,
                    "level": h.level,
                    "text": h.text,
                }
                if h.custom_id:
                    entry["custom_id"] = h.custom_id
                headings.append(entry)

            work[lang] = {
                "file": str(structure.file_path),
                "title": structure.title,
                "author": structure.author,
                "pattern": structure.pattern,
                "heading_count": len(structure.headings),
                "custom_id_count": sum(1 for h in structure.headings if h.custom_id),
                "headings": headings,
            }

        data[stem] = work

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Wrote structure data to {output_path}")
    print(f"  Works: {len(data)}")


def main():
    parser = argparse.ArgumentParser(
        description="Validate heading structure consistency across translation pairs."
    )
    parser.add_argument(
        "mode",
        choices=["check", "report", "json", "untranslated"],
        help="check: exit 0/1 for CI; report: detailed text; json: export structure.json; untranslated: list works without translations",
    )
    parser.add_argument(
        "--severity",
        choices=["info", "warning", "error"],
        default="info",
        help="Minimum severity to fail on (default: info)",
    )
    parser.add_argument(
        "--file",
        metavar="STEM",
        help="Check a single file pair by stem (e.g. alexiada)",
    )
    parser.add_argument(
        "--content-dir",
        type=Path,
        default=None,
        help="Path to the content directory (default: auto-detect)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for json mode (default: public/structure.json)",
    )

    args = parser.parse_args()

    from utils import resolve_content_dir
    content_dir = resolve_content_dir(args.content_dir)

    # Parse all files
    groups = group_files_by_stem(content_dir)

    if args.mode == "json":
        output_path = args.output or (
            content_dir.parent / "public" / "structure.json"
        )
        generate_json(groups, output_path)

    elif args.mode == "untranslated":
        # List works without translations
        greek_no_trans = []
        english_no_source = []
        latin_no_trans = []

        for stem, langs in sorted(groups.items()):
            if 'gr' in langs and len(langs) == 1:
                struct = langs['gr']
                greek_no_trans.append((stem, struct.title, struct.author, struct.file_path))
            if 'en' in langs and 'gr' not in langs and 'la' not in langs:
                struct = langs['en']
                english_no_source.append((stem, struct.title, struct.author, struct.file_path))
            if 'la' in langs and len(langs) == 1:
                struct = langs['la']
                latin_no_trans.append((stem, struct.title, struct.author, struct.file_path))

        print("=" * 70)
        print("  Works Without Translations")
        print("=" * 70)
        print()

        if greek_no_trans:
            print(f"GREEK TEXTS WITHOUT TRANSLATION ({len(greek_no_trans)}):")
            print("-" * 70)
            for stem, title, author, path in greek_no_trans:
                print(f"  {title}")
                print(f"    Author: {author}")
                print(f"    File: {path}")
                print()

        if english_no_source:
            print(f"ENGLISH TEXTS WITHOUT GREEK/LATIN SOURCE ({len(english_no_source)}):")
            print("-" * 70)
            for stem, title, author, path in english_no_source:
                print(f"  {title}")
                print(f"    Author: {author}")
                print(f"    File: {path}")
                print()

        if latin_no_trans:
            print(f"LATIN TEXTS WITHOUT TRANSLATION ({len(latin_no_trans)}):")
            print("-" * 70)
            for stem, title, author, path in latin_no_trans:
                print(f"  {title}")
                print(f"    Author: {author}")
                print(f"    File: {path}")
                print()

        print(f"SUMMARY:")
        print(f"  Greek without translation: {len(greek_no_trans)}")
        print(f"  English without source:    {len(english_no_source)}")
        print(f"  Latin without translation: {len(latin_no_trans)}")
        sys.exit(0)

    elif args.mode in ("check", "report"):
        report, exit_code, failures = generate_report(
            groups,
            min_severity=args.severity,
            file_filter=args.file,
        )

        if args.mode == "report":
            print(report)
        elif args.mode == "check":
            if exit_code != 0:
                # Print concise summary of failures
                error_count = sum(1 for r in failures if r.severity == "error")
                warning_count = sum(1 for r in failures if r.severity == "warning")

                for r in failures:
                    # Determine the brief reason
                    if r.pattern_a != r.pattern_b and r.pattern_a != "none" and r.pattern_b != "none":
                        reason = f"pattern mismatch: {r.pattern_a} vs {r.pattern_b}"
                    else:
                        parts = []
                        if r.ids_only_in_a:
                            parts.append(f"{len(r.ids_only_in_a)} extra in {r.lang_a}")
                        if r.ids_only_in_b:
                            parts.append(f"{len(r.ids_only_in_b)} extra in {r.lang_b}")
                        if not r.order_match:
                            parts.append("order mismatch")
                        reason = ", ".join(parts) if parts else "unknown"

                    # Print the failure summary line
                    print(f"[{r.severity.upper()}] {r.stem} ({r.lang_a} vs {r.lang_b}): {reason}")

                    # Print file paths for both languages
                    if r.stem in groups:
                        for lang_key in sorted(groups[r.stem].keys()):
                            struct = groups[r.stem][lang_key]
                            print(f"  {struct.file_path}")

                print(f"\nFAIL: {len(failures)} file pair(s) with structure mismatches ({error_count} errors, {warning_count} warnings)")
            else:
                print("OK: All translation pairs are structurally consistent.")

        sys.exit(exit_code)


if __name__ == "__main__":
    main()
