#!/usr/bin/env python3
"""
Ensure every translation file has a corresponding original-language file.

English (en/) and Latin (la/) files are translations. Every translation must
have a Greek (gr/) counterpart with the same filename stem - otherwise the
work appears as an orphaned translation in the catalog.

This is bidirectional in principle: if we ever add English originals that
require Greek translations, the same logic applies. The ORIGINAL_DIRS
mapping defines which directories are considered authoritative sources.
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, List, Set

# Map each translation directory to the set of directories that count as
# valid originals. A file in en/ is only valid if gr/ or la/ has the same stem.
# Note: gr/ and la/ are original-language directories and need no counterpart.
TRANSLATION_DIRS: Dict[str, List[str]] = {
    "en": ["gr", "la"],
}


def find_orphans(content_dir: Path) -> List[tuple]:
    """
    Find translation files with no corresponding original.

    Returns list of (file_path, lang_dir, expected_original_dirs).
    """
    # Collect stems per directory
    stems: Dict[str, Set[str]] = {}
    for subdir in sorted(content_dir.iterdir()):
        if not subdir.is_dir():
            continue
        stems[subdir.name] = {
            f.stem for f in subdir.glob("*.org")
            if f.name != "index.org"
            and not f.name.startswith(".")
            and not f.name.startswith("#")
        }

    orphans = []
    for trans_dir, original_dirs in TRANSLATION_DIRS.items():
        if trans_dir not in stems:
            continue

        # Build union of all original stems
        original_stems: Set[str] = set()
        for od in original_dirs:
            if od in stems:
                original_stems |= stems[od]

        # Find translations without originals
        for stem in sorted(stems[trans_dir] - original_stems):
            filepath = content_dir / trans_dir / (stem + ".org")
            orphans.append((filepath, trans_dir, original_dirs))

    return orphans


def main():
    parser = argparse.ArgumentParser(
        description="Ensure every translation has an original-language counterpart."
    )
    parser.add_argument(
        "mode",
        choices=["check", "report"],
        help="check: exit 0/1 for CI; report: detailed output",
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

    orphans = find_orphans(content_dir)

    if args.mode == "report":
        print("=" * 60)
        print("  Original-Language Check")
        print("=" * 60)
        print()
        dirs = ", ".join(
            f"{t}/ requires {'/'.join(o)}/"
            for t, o in sorted(TRANSLATION_DIRS.items())
        )
        print(f"Rules: {dirs}")
        print()

        if orphans:
            print(f"ORPHANED TRANSLATIONS ({len(orphans)}):")
            print("-" * 60)
            for filepath, lang_dir, original_dirs in orphans:
                rel = filepath.relative_to(content_dir)
                expected = " or ".join(f"{d}/" for d in original_dirs)
                print(f"  [ERROR] {rel}")
                print(f"    No counterpart in {expected}")
                print()
        else:
            print("All translations have original-language counterparts.")
        print()

    elif args.mode == "check":
        if orphans:
            for filepath, lang_dir, original_dirs in orphans:
                rel = filepath.relative_to(content_dir)
                expected = " or ".join(f"{d}/" for d in original_dirs)
                print(f"[ERROR] {rel}: no counterpart in {expected}")
            print(f"\nFAIL: {len(orphans)} translation(s) without originals")
            sys.exit(1)
        else:
            print("OK: All translations have original-language counterparts.")
            sys.exit(0)


if __name__ == "__main__":
    main()
