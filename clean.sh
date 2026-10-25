#!/usr/bin/env bash
# ====================================================================
# Clean Script
# Bereinigt generierte Artefakte in 'build/' und 'preview/'
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
            echo "Verwendung: $0 [OPTIONEN]"
            echo ""
            echo "Optionen:"
            echo "  --keep-step, -s      Behält STEP-Dateien in 'build/'"
            echo "  --keep-preview, -p   Behält Screenshots in 'preview/'"
            echo "  -h, --help           Zeigt diese Hilfe an"
            echo ""
            echo "Beispiele:"
            echo "  $0                  # Löscht 'build/' und 'preview/' vollständig"
            echo "  $0 --keep-step      # Löscht STLs und Vorschauen, behält STEPs"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

echo -e "${BOLD}${BLUE}=== Starte Bereinigung ===${NC}"

# 1. Preview-Ordner
if [[ "$KEEP_PREVIEW" == true ]]; then
    echo -e "${YELLOW}Hinweis: 'preview/' wird beibehalten (--keep-preview).${NC}"
else
    if [[ -d "preview" ]]; then
        rm -rf preview
        echo "  ✓ Ordner 'preview/' gelöscht."
    fi
fi

# 2. Build-Ordner
if [[ "$KEEP_STEP" == true ]]; then
    echo -e "${YELLOW}Hinweis: STEP-Dateien in 'build/' werden beibehalten (--keep-step).${NC}"
    if [[ -d "build" ]]; then
        find build -type f ! -name "*.step" ! -name "*.stp" -delete
        echo "  ✓ Nicht-STEP-Dateien in 'build/' gelöscht."
    fi
else
    if [[ -d "build" ]]; then
        rm -rf build
        echo "  ✓ Ordner 'build/' gelöscht."
    fi
fi

# 3. Alte Artefakte im Root-Verzeichnis bereinigen falls vorhanden
find . -maxdepth 1 -name "*.stl" -o -name "*.step" -o -name "*.stp" -o -name "*.png" | while read -r f; do
    rm -f "$f"
    echo "  ✓ Root-Datei gelöscht: $(basename "$f")"
done

# 4. Cache
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

echo -e "\n${BOLD}${GREEN}✔ Bereinigung abgeschlossen!${NC}"
