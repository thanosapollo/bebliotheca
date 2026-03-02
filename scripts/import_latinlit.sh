#!/bin/sh
# Import/update content from Perseus Latin Literature submodule.
#
# Usage:
#   ./scripts/import_latinlit.sh            Re-import from pinned submodule commit
#   ./scripts/import_latinlit.sh --update   Update submodule to latest upstream first
#
# Pipeline: init submodule → convert XML → remove stale files → copy → tag → manifest → cleanup → test
set -e

SCRIPTS_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPTS_DIR/.." && pwd)"
SUBMODULE="$ROOT_DIR/sources/canonical-latinLit"
CONVERTER="$SCRIPTS_DIR/convert_perseus_xml_to_org.py"
CONTENT_DIR="$ROOT_DIR/content"
MANIFEST="$ROOT_DIR/sources/latinlit-manifest.txt"

# Step 1: Ensure submodule is initialized
echo "==> Initializing submodule"
git -C "$ROOT_DIR" submodule update --init sources/canonical-latinLit

# Step 2: Optionally update to latest upstream
if [ "$1" = "--update" ]; then
    echo "==> Updating to latest upstream"
    git -C "$SUBMODULE" fetch origin
    git -C "$SUBMODULE" checkout origin/master
    echo "    Now at: $(git -C "$SUBMODULE" log --oneline -1)"
fi

# Step 3: Clean previous converter output
echo "==> Cleaning converter output directories"
rm -rf "$SUBMODULE/gr" "$SUBMODULE/en" "$SUBMODULE/la"

# Step 4: Run converter
echo "==> Converting TEI XML to Org"
(cd "$SUBMODULE" && python3 "$CONVERTER")

# Step 5: Delete all files from previous manifest (clean slate)
if [ -f "$MANIFEST" ]; then
    echo "==> Removing old files listed in manifest"
    count=0
    while IFS= read -r old_file; do
        rm -f "$ROOT_DIR/$old_file"
        count=$((count + 1))
    done < "$MANIFEST"
    echo "    Removed $count files"
fi

# Step 6: Copy fresh converter output to content/
echo "==> Copying to content/"
# Latin originals
if [ -d "$SUBMODULE/la" ]; then
    mkdir -p "$CONTENT_DIR/la"
    cp -r "$SUBMODULE/la/"* "$CONTENT_DIR/la/" 2>/dev/null || true
fi
# English translations
if [ -d "$SUBMODULE/en" ]; then
    mkdir -p "$CONTENT_DIR/en"
    cp -r "$SUBMODULE/en/"* "$CONTENT_DIR/en/" 2>/dev/null || true
fi
# Greek (unlikely but handle if present — e.g. Greek translations of Latin works)
if [ -d "$SUBMODULE/gr" ]; then
    mkdir -p "$CONTENT_DIR/gr"
    cp -r "$SUBMODULE/gr/"* "$CONTENT_DIR/gr/" 2>/dev/null || true
fi

# Step 7: Tag files with FILETAGS
echo "==> Tagging files"
(cd "$ROOT_DIR" && python3 "$SCRIPTS_DIR/tag_filetags.py")

# Step 8: Generate manifest
echo "==> Generating manifest"
{
    for lang in la en gr; do
        if [ -d "$SUBMODULE/$lang" ]; then
            for f in "$SUBMODULE"/$lang/*.org; do
                [ -f "$f" ] && echo "content/$lang/$(basename "$f")"
            done
        fi
    done
} | sort > "$MANIFEST"
count=$(wc -l < "$MANIFEST" | tr -d ' ')
echo "    $count files in manifest"

# Step 9: Clean converter output (don't leave untracked files in submodule)
echo "==> Cleaning converter output"
rm -rf "$SUBMODULE/gr" "$SUBMODULE/en" "$SUBMODULE/la"

# Step 10: Run tests
echo "==> Running validation"
(cd "$ROOT_DIR" && make test)

echo "==> Import complete"
if [ "$1" = "--update" ]; then
    echo "    Submodule updated. Remember to stage the new pinned commit:"
    echo "      git add sources/canonical-latinLit"
fi
