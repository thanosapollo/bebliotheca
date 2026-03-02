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

ALL_DIRS="$CONTENT_DIR/gr $CONTENT_DIR/en $CONTENT_DIR/la"

case "${1:-all}" in
    all)
        echo "==> Cleaning previous build"
        "$0" clean
        echo "==> Generating catalog"
        python3 generate_catalog.py
        echo "==> Exporting all content"
        count=$(find_all $ALL_DIRS | tr '\0' '\n' | wc -l)
        echo "Exporting $count files ($JOBS parallel jobs, batches of $BATCH_SIZE)"
        find_all $ALL_DIRS | export_files
        echo "==> Done"
        ;;
    catalog)
        python3 generate_catalog.py
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
        rm -f "$PUBLIC_DIR/catalog.json"
        echo "Cleaned"
        ;;
    clean-sources)
        for manifest in sources/*-manifest.txt; do
            [ -f "$manifest" ] || continue
            count=0
            while IFS= read -r f; do
                rm -f "$f"
                count=$((count + 1))
            done < "$manifest"
            echo "Removed $count files ($(basename "$manifest"))"
        done
        ;;
    import)
        for script in scripts/import_*.sh; do
            [ -f "$script" ] || continue
            echo "==> Running $(basename "$script")"
            "$script"
        done
        ;;
    update)
        git submodule update --remote
        "$0" import
        ;;
    publish)
        "$0" import
        "$0" all
        ./publish.sh
        ;;
    publish-update)
        "$0" update
        "$0" all
        ./publish.sh
        ;;
    help|-h|--help)
        echo "Usage: $0 [all|catalog|export|gr|en|la|clean|clean-sources|import|update|publish|publish-update|help]"
        echo ""
        echo "  all            Clean + catalog + full export (default)"
        echo "  catalog        Generate catalog.json"
        echo "  export         Incremental export (only changed files)"
        echo "  gr             Export Greek content only"
        echo "  en             Export English content only"
        echo "  la             Export Latin content only"
        echo "  clean          Remove generated HTML + catalog"
        echo "  clean-sources  Remove auto-generated .org files from all sources"
        echo "  import         Import content from all source submodules"
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
