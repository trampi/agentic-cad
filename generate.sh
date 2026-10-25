#!/usr/bin/env bash
# ====================================================================
# CAD Build Script (Python / build123d) - Optimiert für AGENTIC CODING
# Generiert:
#   - build/   : STEP-Dateien (Autodesk Fusion), STL-Dateien & metrics.json
#   - preview/ : Multi-View Renderings (Iso, Top, Front, Side, Quad-Collage)
# ====================================================================

set -euo pipefail

GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BOLD="\033[1m"
NC="\033[0m"

# Hilfe anzeigen
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
    echo -e "${BOLD}${BLUE}Verwendung:${NC} $0 [OPTIONEN]"
    echo ""
    echo "Optionen für schnelles Agentic Coding & Iteration:"
    echo "  --fast, --no-step     Schnelliteration: Überspringt STEP-Export (nur STL & Previews in <1s)"
    echo "  --part TEIL           Baut nur ein Teil: 'wandhalterung', 'haltehaken', 'baugruppe', 'all' (Standard: all)"
    echo "  --views MODUS         Rendering-Modus: 'quad' (nur 4-in-1 Collage), 'all' (Collage + Einzelansichten),"
    echo "                        'iso' (nur 3D-Ansicht), 'none' (keine Renderings)"
    echo "  --json                Generiert strukturierte Metriken in 'build/metrics.json'"
    echo ""
    echo "Geometrie-Parameter direkt überschreiben:"
    echo "  --spiel MM            Gleitspiel Schwalbenschwanz (Standard: 0.35 mm)"
    echo "  --neigung GRAD        Neigungswinkel nach oben (Standard: 5.0 Grad)"
    echo "  --dorn-l MM           Nutzlänge des Dorns (Standard: 50.0 mm)"
    echo "  --dorn-d MM           Durchmesser des Dorns (Standard: 16.0 mm)"
    echo "  --kragen-d MM         Durchmesser Abschlusskragen (Standard: 24.0 mm)"
    echo ""
    echo "Beispiele:"
    echo "  $0                    # Standard-Full-Build (STEP, STL, alle Multi-Views & Sanity-Checks)"
    echo "  $0 --fast             # Schneller Testlauf: STL + Previews ohne teuren STEP-Export"
    echo "  $0 --fast --part haltehaken --views quad  # Ultra-schnelle Iteration nur am Haken"
    echo "  $0 --spiel 0.30       # Build mit 0.30 mm Spiel testen"
    exit 0
fi

# Python 3 prüfen
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}[Fehler] python3 ist nicht installiert.${NC}" >&2
    exit 1
fi

# build123d prüfen
if ! python3 -c "import build123d" &>/dev/null; then
    echo -e "${RED}[Fehler] build123d ist nicht installiert.${NC}" >&2
    echo "Installiere es mit: pip install build123d" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="${SCRIPT_DIR}/schlauch_halteplatte_dorn.py"

echo -e "${BOLD}${BLUE}=== Starte Build (build123d / Python) ===${NC}"

# Python-Skript mit allen übergebenen CLI-Parametern ausführen
python3 "$PY_SCRIPT" "$@"

echo -e "\n${BOLD}${GREEN}✔ Fertig! Artefakte liegen in 'build/' und 'preview/'${NC}"
