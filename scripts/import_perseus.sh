#!/bin/sh
# Import/update content from Perseus Digital Library submodule.
#
# Usage:
#   ./scripts/import_perseus.sh            Re-import from pinned submodule commit
#   ./scripts/import_perseus.sh --update   Update submodule to latest upstream first
#
# Pipeline: init submodule → convert XML → remove stale files → copy → hellenize → manifest → cleanup → test
set -e

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPTS_DIR/.." && pwd)"
SUBMODULE="$ROOT_DIR/sources/canonical-greekLit"
CONVERTER="$SCRIPTS_DIR/convert_perseus_xml_to_org.py"
HELLENIZE="$SCRIPTS_DIR/hellenize_headings.py"
CONTENT_DIR="$ROOT_DIR/content"
MANIFEST="$ROOT_DIR/sources/perseus-manifest.txt"

# Step 1: Ensure submodule is initialized
echo "==> Initializing submodule"
git -C "$ROOT_DIR" submodule update --init sources/canonical-greekLit

# Step 2: Optionally update to latest upstream
if [ "$1" = "--update" ]; then
    echo "==> Updating to latest Perseus upstream"
    git -C "$SUBMODULE" fetch origin
    git -C "$SUBMODULE" checkout origin/master
    echo "    Now at: $(git -C "$SUBMODULE" log --oneline -1)"
fi

# Step 3: Clean previous converter output
echo "==> Cleaning converter output directories"
rm -rf "$SUBMODULE/gr" "$SUBMODULE/en"

# Step 4: Run converter
echo "==> Converting TEI XML to Org"
(cd "$SUBMODULE" && python3 "$CONVERTER")

# Step 5: Delete all files from previous manifest (clean slate for Perseus files)
if [ -f "$MANIFEST" ]; then
    echo "==> Removing old Perseus files listed in manifest"
    count=0
    while IFS= read -r old_file; do
        rm -f "$ROOT_DIR/$old_file"
        count=$((count + 1))
    done < "$MANIFEST"
    echo "    Removed $count files"
fi

# Step 6: Copy fresh converter output to content/
echo "==> Copying to content/"
cp -r "$SUBMODULE/gr/"* "$CONTENT_DIR/gr/"
cp -r "$SUBMODULE/en/"* "$CONTENT_DIR/en/"

# Step 7: Hellenize Greek headings
echo "==> Hellenizing Greek headings"
(cd "$ROOT_DIR" && python3 "$HELLENIZE")

# Step 8: Generate manifest
echo "==> Generating manifest"
{
    for f in "$SUBMODULE"/gr/*.org; do
        [ -f "$f" ] && echo "content/gr/$(basename "$f")"
    done
    for f in "$SUBMODULE"/en/*.org; do
        [ -f "$f" ] && echo "content/en/$(basename "$f")"
    done
} | sort > "$MANIFEST"
count=$(wc -l < "$MANIFEST" | tr -d ' ')
echo "    $count files in manifest"

# Step 9: Clean converter output (don't leave untracked files in submodule)
echo "==> Cleaning converter output"
rm -rf "$SUBMODULE/gr" "$SUBMODULE/en"

# Step 10: Run tests
echo "==> Running validation"
(cd "$ROOT_DIR" && make test)

echo "==> Import complete"
if [ "$1" = "--update" ]; then
    echo "    Submodule updated. Remember to stage the new pinned commit:"
    echo "      git add sources/canonical-greekLit"
fi
