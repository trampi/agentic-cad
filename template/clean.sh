#!/usr/bin/env bash
# ====================================================================
# Clean Script
# Removes generated artifacts in 'build/' and 'preview/'
# ====================================================================

set -euo pipefail

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
BOLD="\033[1m"
NC="\033[0m"

KEEP_STEP=false
KEEP_PREVIEW=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --keep-step|-s)
            KEEP_STEP=true
            shift
            ;;
        --keep-preview|-p)
            KEEP_PREVIEW=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --keep-step, -s      Keep STEP files in 'build/'"
            echo "  --keep-preview, -p   Keep preview images in 'preview/'"
            echo "  -h, --help           Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                  # Remove 'build/' and 'preview/' completely"
            echo "  $0 --keep-step      # Remove STLs and previews, preserve STEPs"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

echo -e "${BOLD}${BLUE}=== Starting Cleanup ===${NC}"

# 1. Preview directory
if [[ "$KEEP_PREVIEW" == true ]]; then
    echo -e "${YELLOW}Note: Keeping 'preview/' (--keep-preview).${NC}"
else
    if [[ -d "preview" ]]; then
        rm -rf preview
        echo "  ✓ Removed 'preview/' directory."
    fi
fi

# 2. Build directory
if [[ "$KEEP_STEP" == true ]]; then
    echo -e "${YELLOW}Note: Keeping STEP files in 'build/' (--keep-step).${NC}"
    if [[ -d "build" ]]; then
        find build -type f ! -name "*.step" ! -name "*.stp" -delete
        echo "  ✓ Removed non-STEP files in 'build/'."
    fi
else
    if [[ -d "build" ]]; then
        rm -rf build
        echo "  ✓ Removed 'build/' directory."
    fi
fi

# 3. Clean up any loose artifacts in the project root if present
find . -maxdepth 1 \( -name "*.stl" -o -name "*.step" -o -name "*.stp" -o -name "*.png" \) | while read -r f; do
    rm -f "$f"
    echo "  ✓ Removed loose file: $(basename "$f")"
done

# 4. Python cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo -e "\n${BOLD}${GREEN}✔ Cleanup complete!${NC}"
