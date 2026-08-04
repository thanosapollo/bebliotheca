#!/bin/sh
#
# Bebliotheca Build Script
# Exports .org files to HTML using batched parallel Emacs processes
#
set -e

EMACS="${EMACS:-emacs}"
CONTENT_DIR="content"
PUBLIC_DIR="public"
JOBS="${JOBS:-$(nproc 2>/dev/null || echo 4)}"
BATCH_SIZE="${BATCH_SIZE:-100}"
EXPORT_EL="build-export.el"

# Export .org files read from stdin (null-delimited) using batched Emacs
export_files() {
    xargs -0 -r -n "$BATCH_SIZE" -P "$JOBS" \
        "$EMACS" --batch -Q --load "$EXPORT_EL" --
}

# Collect all .org files from given directories (null-delimited to stdout)
find_all() {
    for dir in "$@"; do
        [ -d "$dir" ] || continue
        find "$dir" -maxdepth 1 -name '*.org' -not -name 'index.org' -type f -print0
    done
}

# Collect only .org files whose HTML is missing or older than source
find_changed() {
    for dir in "$@"; do
        [ -d "$dir" ] || continue
        lang=$(basename "$dir")
        for org in "$dir"/*.org; do
            [ -f "$org" ] || continue
            stem=$(basename "$org" .org)
            [ "$stem" = "index" ] && continue
            html="$PUBLIC_DIR/$lang/$stem.html"
            if [ ! -f "$html" ] || [ "$org" -nt "$html" ]; then
                printf '%s\0' "$org"
            fi
        done
    done
}

# Export a single language directory (all files)
export_dir() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        echo "Warning: $dir does not exist, skipping"
        return
    fi
    local count
    count=$(find "$dir" -maxdepth 1 -name '*.org' -not -name 'index.org' -type f | wc -l)
    echo "Exporting $count files from $dir ($JOBS parallel jobs, batches of $BATCH_SIZE)"
    find "$dir" -maxdepth 1 -name '*.org' -not -name 'index.org' -type f -print0 | \
        export_files
}

PG_MIGNE_DIR="sources/pg-migne"
PDF_MANIFEST="log/pg-migne-pdf-manifest.json"

# Copy PG Migne PDFs to public/gr/ using the JSON manifest.
# Skips silently if the source directory or manifest doesn't exist
# (PDFs are not tracked in git).
copy_pdfs() {
    [ -d "$PG_MIGNE_DIR" ] || return 0
    [ -f "$PDF_MANIFEST" ] || return 0
    echo "==> Copying PG Migne PDFs"
    python3 -c "
import json, shutil, sys
from pathlib import Path
manifest = json.load(open('$PDF_MANIFEST'))
copied = 0
for org_name, pdf_rel in manifest.items():
    src = Path('$PG_MIGNE_DIR') / pdf_rel
    if not src.exists():
        continue
    stem = org_name.replace('.org', '')
    dst = Path('$PUBLIC_DIR/gr') / (stem + '.pdf')
    if dst.exists():
        continue
    shutil.copy2(src, dst)
    copied += 1
print(f'Copied {copied} PDFs to $PUBLIC_DIR/gr/')
"
}

ALL_DIRS="$CONTENT_DIR/gr $CONTENT_DIR/en $CONTENT_DIR/la"

case "${1:-all}" in
    all)
        echo "==> Cleaning previous build"
        "$0" clean
        echo "==> Generating catalog + index"
        python3 scripts/generate_catalog.py
        python3 scripts/generate_index.py --quiet
        echo "==> Exporting all content"
        count=$(find_all $ALL_DIRS | tr '\0' '\n' | wc -l)
        echo "Exporting $count files ($JOBS parallel jobs, batches of $BATCH_SIZE)"
        find_all $ALL_DIRS | export_files
        echo "==> Done"
        ;;
    catalog)
        python3 scripts/generate_catalog.py
        python3 scripts/generate_index.py --quiet
        ;;
    index)
        python3 scripts/generate_index.py
        ;;
    export)
        echo "==> Incremental export (changed files only)"
        tmp=$(mktemp)
        find_changed $ALL_DIRS > "$tmp"
        count=$(tr '\0' '\n' < "$tmp" | wc -l)
        if [ "$count" -eq 0 ]; then
            echo "No files to export — everything up to date"
        else
            echo "Exporting $count changed files ($JOBS parallel jobs, batches of $BATCH_SIZE)"
            cat "$tmp" | export_files
        fi
        rm -f "$tmp"
        # Remove orphaned HTML (no matching .org source)
        stale=0
        for lang in gr en la; do
            [ -d "$PUBLIC_DIR/$lang" ] || continue
            for html in "$PUBLIC_DIR/$lang"/*.html; do
                [ -f "$html" ] || continue
                stem=$(basename "$html" .html)
                if [ ! -f "$CONTENT_DIR/$lang/$stem.org" ]; then
                    rm -f "$html"
                    stale=$((stale + 1))
                fi
            done
        done
        [ "$stale" -gt 0 ] && echo "Removed $stale orphaned HTML files"
        echo "==> Done"
        ;;
    gr|greek)
        export_dir "$CONTENT_DIR/gr"
        ;;
    en|english)
        export_dir "$CONTENT_DIR/en"
        ;;
    la|latin)
        export_dir "$CONTENT_DIR/la"
        ;;
    clean)
        find "$PUBLIC_DIR/gr" "$PUBLIC_DIR/en" "$PUBLIC_DIR/la" -name '*.html' -delete 2>/dev/null || true
        find "$PUBLIC_DIR/gr" -name '*.pdf' -delete 2>/dev/null || true
        rm -f "$PUBLIC_DIR/catalog.json" "$PUBLIC_DIR/catalog-static.html"
        echo "Cleaned"
        ;;
    clean-sources)
        echo "WARNING: This deletes tracked .org files from content/."
        echo "They can be restored with: git checkout -- content/"
        for manifest in log/*-manifest.txt; do
            [ -f "$manifest" ] || continue
            count=0
            while IFS= read -r f; do
                rm -f "$f"
                count=$((count + 1))
            done < "$manifest"
            echo "Removed $count files ($(basename "$manifest"))"
        done
        ;;
    report)
        mkdir -p log
        python3 tests/check_structure.py report > log/structure-report.txt || true
        python3 tests/check_language.py report > log/language-report.txt || true
        python3 tests/check_originals.py report > log/originals-report.txt || true
        python3 tests/check_metadata.py report > log/metadata-report.txt || true
        echo "Reports written to log/"
        ;;
    import)
        python3 scripts/import_sources.py
        ;;
    update)
        python3 scripts/import_sources.py --update
        ;;
    copy-pdfs)
        copy_pdfs
        ;;
    publish)
        "$0" all
        ./publish.sh
        ;;
    publish-update)
        "$0" update
        "$0" all
        ./publish.sh
        ;;
    help|-h|--help)
        echo "Usage: $0 [all|catalog|index|export|gr|en|la|clean|clean-sources|copy-pdfs|report|import|update|publish|publish-update|help]"
        echo ""
        echo "  all            Clean + catalog + index + full export (default)"
        echo "  catalog        Generate catalog.json + index.org files"
        echo "  index          Generate per-language index.org files"
        echo "  export         Incremental export (only changed files)"
        echo "  gr             Export Greek content only"
        echo "  en             Export English content only"
        echo "  la             Export Latin content only"
        echo "  clean          Remove generated HTML + catalog"
        echo "  clean-sources  Remove tracked .org files listed in manifests"
        echo "  copy-pdfs      Copy PG Migne PDFs to public/gr/ (requires sources/pg-migne/)"
        echo "  report         Write test reports to log/"
        echo "  import         Import new files from source submodules (skips existing)"
        echo "  update         Update all submodules to latest and re-import"
        echo "  publish        Import + build + deploy to server"
        echo "  publish-update Update sources, build, and deploy"
        echo "  help           Show this help"
        echo ""
        echo "Environment: JOBS=$JOBS BATCH_SIZE=$BATCH_SIZE EMACS=$EMACS"
        ;;
    *)
        echo "Unknown target: $1"
        echo "Run '$0 help' for usage"
        exit 1
        ;;
esac
