#!/usr/bin/env python3
"""
Detect files whose content script doesn't match their directory.

General-purpose language placement test. Checks that files in each language
directory contain text in the expected script (e.g., Greek script in gr/,
Latin script in en/ and la/).

To add a new language:
  1. Add an entry to DIRECTORY_SCRIPTS (e.g., "cop": "coptic")
  2. Add the Unicode range to SCRIPT_RANGES (e.g., "coptic": [(0x2C80, 0x2CFF)])
"""

import argparse
import random
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Unicode ranges for each script family
SCRIPT_RANGES: Dict[str, List[Tuple[int, int]]] = {
    "greek": [
        (0x0370, 0x03FF),  # Greek and Coptic
        (0x1F00, 0x1FFF),  # Greek Extended
    ],
    "latin": [
        (0x0041, 0x005A),  # A-Z
        (0x0061, 0x007A),  # a-z
        (0x00C0, 0x024F),  # Latin Extended-A/B
    ],
}

# Map directory name to expected dominant script
DIRECTORY_SCRIPTS: Dict[str, str] = {
    "gr": "greek",
    "en": "latin",
    "la": "latin",
}


def classify_char(c: str) -> Optional[str]:
    """Return the script name for a character, or None if unrecognized."""
    cp = ord(c)
    for script, ranges in SCRIPT_RANGES.items():
        for lo, hi in ranges:
            if lo <= cp <= hi:
                return script
    return None


def detect_dominant_script(text: str) -> Tuple[Optional[str], float]:
    """
    Detect the dominant script in a text.

    Returns (script_name, ratio) where ratio is the fraction of classified
    alphabetic characters belonging to the dominant script. Returns (None, 0.0)
    if no classifiable characters are found.
    """
    counts: Dict[str, int] = {}
    total = 0

    for c in text:
        script = classify_char(c)
        if script is not None:
            counts[script] = counts.get(script, 0) + 1
            total += 1

    if total == 0:
        return None, 0.0

    dominant = max(counts, key=counts.get)
    return dominant, counts[dominant] / total


def extract_heading_sections(file_path: Path) -> List[str]:
    """
    Extract text content under each heading in an .org file.

    Returns a list of text blocks, one per heading. Org metadata, PROPERTIES
    drawers, and markup directives are excluded.
    """
    heading_re = re.compile(r"^(\*+)\s+(.+)$")
    sections: List[str] = []
    current_lines: List[str] = []
    in_heading_content = False
    in_properties = False
    in_block = False

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()

            # Skip org-mode directives
            if stripped.startswith("#+"):
                continue

            # Track block environments (quote, src, etc.)
            if stripped.upper().startswith("#+BEGIN_"):
                in_block = True
                continue
            if stripped.upper().startswith("#+END_"):
                in_block = False
                continue

            # Track PROPERTIES drawers
            if stripped == ":PROPERTIES:":
                in_properties = True
                continue
            if stripped == ":END:":
                in_properties = False
                continue
            if in_properties:
                continue

            # Detect headings
            if heading_re.match(stripped):
                if in_heading_content and current_lines:
                    sections.append("\n".join(current_lines))
                current_lines = []
                in_heading_content = True
                continue

            # Collect content lines (skip blocks, empty lines, line numbers)
            if in_heading_content and not in_block:
                # Strip org line-number markup like =1= at start of line
                content = re.sub(r"^=\d+=\s*", "", stripped)
                if content:
                    current_lines.append(content)

    # Don't forget the last section
    if in_heading_content and current_lines:
        sections.append("\n".join(current_lines))

    return sections


def check_file(
    file_path: Path,
    expected_script: str,
    sample_count: int = 5,
    threshold: float = 0.70,
    seed: Optional[int] = None,
) -> Tuple[bool, Optional[str], float, int]:
    """
    Check whether a file's dominant script matches the expected script.

    Returns:
        (is_misplaced, dominant_script, dominant_ratio, sections_sampled)
    """
    sections = extract_heading_sections(file_path)

    if not sections:
        return False, None, 0.0, 0

    # Sample random sections
    rng = random.Random(seed)
    sample_size = min(sample_count, len(sections))
    sampled = rng.sample(sections, sample_size)

    # Combine sampled text and detect dominant script
    combined = "\n".join(sampled)
    dominant, ratio = detect_dominant_script(combined)

    if dominant is None:
        return False, None, 0.0, sample_size

    # Misplaced if dominant script differs from expected AND exceeds threshold
    is_misplaced = dominant != expected_script and ratio >= threshold
    return is_misplaced, dominant, ratio, sample_size


def scan_all(
    content_dir: Path,
    sample_count: int = 5,
    threshold: float = 0.70,
    seed: int = 42,
) -> List[Tuple[Path, str, str, float, int]]:
    """
    Scan all language directories for misfiled texts.

    Returns list of (file_path, expected_script, dominant_script, ratio, sections_sampled).
    """
    misplaced = []

    for lang_dir in sorted(content_dir.iterdir()):
        if not lang_dir.is_dir():
            continue
        if lang_dir.name not in DIRECTORY_SCRIPTS:
            continue

        expected = DIRECTORY_SCRIPTS[lang_dir.name]

        for org_file in sorted(lang_dir.glob("*.org")):
            if org_file.name.startswith(".") or org_file.name.startswith("#"):
                continue
            if org_file.name == "index.org":
                continue

            is_misplaced, dominant, ratio, sampled = check_file(
                org_file,
                expected_script=expected,
                sample_count=sample_count,
                threshold=threshold,
                seed=seed,
            )

            if is_misplaced:
                misplaced.append((org_file, expected, dominant, ratio, sampled))

    return misplaced


def main():
    parser = argparse.ArgumentParser(
        description="Detect files whose content script doesn't match their directory."
    )
    parser.add_argument(
        "mode",
        choices=["check", "report"],
        help="check: exit 0/1 for CI; report: detailed output",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=5,
        help="Number of random heading sections to sample per file (default: 5)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.70,
        help="Dominant script ratio threshold (default: 0.70)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling (default: 42)",
    )
    parser.add_argument(
        "--content-dir",
        type=Path,
        default=None,
        help="Path to the content directory (default: auto-detect)",
    )

    args = parser.parse_args()

    from utils import resolve_content_dir
    content_dir = resolve_content_dir(args.content_dir)

    misplaced = scan_all(
        content_dir,
        sample_count=args.samples,
        threshold=args.threshold,
        seed=args.seed,
    )

    script_labels = {v: k for k, v in DIRECTORY_SCRIPTS.items()}

    if args.mode == "report":
        print("=" * 60)
        print("  Language Placement Check")
        print("=" * 60)
        print()
        dirs = ", ".join(f"{d}/={s}" for d, s in sorted(DIRECTORY_SCRIPTS.items()))
        print(f"Directories: {dirs}")
        print(f"Settings: {args.samples} samples, {args.threshold:.0%} threshold, seed={args.seed}")
        print()

        if misplaced:
            print(f"MISPLACED FILES ({len(misplaced)}):")
            print("-" * 60)
            for file_path, expected, dominant, ratio, sampled in misplaced:
                rel = file_path.relative_to(content_dir)
                print(f"  [ERROR] {rel}")
                print(f"    Expected: {expected}, detected: {dominant} ({ratio:.1%})")
                print(f"    Sections sampled: {sampled}")
                print()
        else:
            print("All files are in the correct language directory.")
        print()

    elif args.mode == "check":
        if misplaced:
            for file_path, expected, dominant, ratio, sampled in misplaced:
                rel = file_path.relative_to(content_dir)
                print(f"[ERROR] {rel}: expected {expected}, detected {dominant} ({ratio:.0%}, {sampled} sections)")
            print(f"\nFAIL: {len(misplaced)} file(s) in wrong language directory")
            sys.exit(1)
        else:
            print("OK: All files match their language directory.")
            sys.exit(0)


if __name__ == "__main__":
    main()
