"""Shared utilities for Bebliotheca test scripts."""

import sys
from pathlib import Path
from typing import Optional


def resolve_content_dir(override: Optional[Path] = None) -> Path:
    """
    Resolve the content directory from an explicit path, script location, or CWD.

    Args:
        override: Explicit path from --content-dir argument, if provided.

    Returns:
        Path to the content/ directory.

    Raises:
        SystemExit: If no content directory can be found.
    """
    if override:
        if not override.exists():
            print(f"Error: Content directory not found: {override}", file=sys.stderr)
            sys.exit(1)
        return override

    # Try relative to the caller's script location (tests/ -> project root)
    script_dir = Path(__file__).resolve().parent
    candidate = script_dir.parent / "content"
    if candidate.exists():
        return candidate

    # Fallback: CWD
    if Path("content").exists():
        return Path("content")

    print("Error: Cannot find content directory.", file=sys.stderr)
    print("  Run from project root or use --content-dir", file=sys.stderr)
    sys.exit(1)
