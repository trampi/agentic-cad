#!/usr/bin/env bash
# ====================================================================
# Clean Script
# Entfernt generierte Build-Artefakte (STL, STEP, PNG, PyCache)
# ====================================================================

set -euo pipefail

GREEN="\033[0;32m"
YELLOW="\033[1;33m"
BLUE="\033[0;34m"
BOLD="\033[1m"
NC="\033[0m"

KEEP_STEP=false
TARGET_DIR="."

# Parameter parsen
while [[ $# -gt 0 ]]; do
    case "$1" in
        --keep-step|-s)
            KEEP_STEP=true
            shift
            ;;
        -h|--help)
            echo "Verwendung: $0 [OPTIONEN] [VERZEICHNIS]"
            echo ""
            echo "Optionen:"
            echo "  --keep-step, -s   Löscht STL-, PNG- und Cache-Dateien, behält aber STEP-Dateien"
            echo "  -h, --help        Zeigt diese Hilfe an"
            echo ""
            echo "Beispiele:"
            echo "  $0               # Löscht alle generierten Dateien (STL, STEP, PNG)"
            echo "  $0 --keep-step   # Löscht STL & PNG, behält STEP für Fusion"
            exit 0
            ;;
        *)
            TARGET_DIR="$1"
            shift
            ;;
    esac
done

echo -e "${BOLD}${BLUE}=== Starte Bereinigung in '${TARGET_DIR}' ===${NC}"

PATTERNS=("*.stl" "*.png")

if [[ "$KEEP_STEP" == true ]]; then
    echo -e "${YELLOW}Hinweis: STEP-Dateien werden beibehalten (--keep-step).${NC}"
else
    PATTERNS+=("*.step" "*.stp")
fi

COUNT=0

for pattern in "${PATTERNS[@]}"; do
    # Nullglob-Verhalten simulieren
    for file in "${TARGET_DIR}"/$pattern; do
        if [[ -f "$file" ]]; then
            rm -f "$file"
            echo "  ✓ Gelöscht: $(basename "$file")"
            COUNT=$((COUNT + 1))
        fi
    done
done

# __pycache__ Verzeichnisse bereinigen
find "${TARGET_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

if [[ $COUNT -eq 0 ]]; then
    echo -e "${GREEN}Verzeichnis ist bereits sauber (keine zu löschenden Dateien gefunden).${NC}"
else
    echo -e "\n${BOLD}${GREEN}✔ Bereinigung abgeschlossen: ${COUNT} Datei(en) gelöscht.${NC}"
fi
