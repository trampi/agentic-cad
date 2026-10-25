#!/usr/bin/env bash
# ====================================================================
# CAD Build Script (Python / build123d)
# Generiert STEP-Dateien (für Autodesk Fusion) und STL-Dateien (3D-Druck)
# ====================================================================

set -euo pipefail

# ANSI-Farben
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BOLD="\033[1m"
NC="\033[0m"

OUTPUT_DIR="${1:-.}"

mkdir -p "$OUTPUT_DIR"

# Python 3 prüfen
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}[Fehler] python3 ist nicht installiert.${NC}" >&2
    exit 1
fi

# build123d prüfen
if ! python3 -c "import build123d" &>/dev/null; then
    echo -e "${RED}[Fehler] build123d ist in Python nicht installiert.${NC}" >&2
    echo "Installiere es mit: pip install build123d" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="${SCRIPT_DIR}/schlauch_halteplatte_dorn.py"

if [[ ! -f "$PY_SCRIPT" ]]; then
    echo -e "${RED}[Fehler] Skript '$PY_SCRIPT' nicht gefunden.${NC}" >&2
    exit 1
fi

echo -e "${BOLD}${BLUE}=== Starte Build (build123d / Python) ===${NC}"

python3 "$PY_SCRIPT"

echo -e "\n${BOLD}${GREEN}✔ Build erfolgreich abgeschlossen!${NC}"
