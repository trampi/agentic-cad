#!/usr/bin/env bash
# ====================================================================
# OpenSCAD Build & Render Script
# Generiert STL-Dateien (Wandhalterung, Dorn-Einschub, Komplettset)
# und PNG-Renderings (Explosionsansicht, Zusammenbau, Einzelteile)
# ====================================================================

set -euo pipefail

# ANSI-Farben
GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BOLD="\033[1m"
NC="\033[0m"

SCAD_FILE="${1:-schlauch_halteplatte_dorn.scad}"
OUTPUT_DIR="${2:-.}"
IMG_SIZE="1200,900"
COLOR_SCHEME="Cornfield"

mkdir -p "$OUTPUT_DIR"

if ! command -v openscad &>/dev/null; then
    echo -e "${RED}[Fehler] OpenSCAD ist nicht installiert.${NC}" >&2
    exit 1
fi

if [[ ! -f "$SCAD_FILE" ]]; then
    echo -e "${RED}[Fehler] Datei '$SCAD_FILE' nicht gefunden.${NC}" >&2
    exit 1
fi

echo -e "${BOLD}${BLUE}=== Starte Build für modulares Schnellwechselsystem ===${NC}"

# 1. STL: Wandhalterung (Basis am Schrank)
echo -e "\n${YELLOW}▶ Exportiere STL: Wandhalterung (Schrank)...${NC}"
openscad -D 'ansicht="wandhalterung"' -o "${OUTPUT_DIR}/wandhalterung.stl" "$SCAD_FILE"
echo -e "${GREEN}✓ ${OUTPUT_DIR}/wandhalterung.stl ($(du -h "${OUTPUT_DIR}/wandhalterung.stl" | cut -f1))${NC}"

# 2. STL: Dorn-Einschub (abnehmbarer Schlitten)
echo -e "\n${YELLOW}▶ Exportiere STL: Dorn-Einschub (abnehmbar)...${NC}"
openscad -D 'ansicht="dorn_einschub"' -o "${OUTPUT_DIR}/dorn_einschub.stl" "$SCAD_FILE"
echo -e "${GREEN}✓ ${OUTPUT_DIR}/dorn_einschub.stl ($(du -h "${OUTPUT_DIR}/dorn_einschub.stl" | cut -f1))${NC}"

# 3. STL: Beide Teile auf Druckbett (gemeinsamer Druck)
echo -e "\n${YELLOW}▶ Exportiere STL: Beide Teile auf Druckbett...${NC}"
openscad -D 'ansicht="beide"' -o "${OUTPUT_DIR}/beide_druckbett.stl" "$SCAD_FILE"
echo -e "${GREEN}✓ ${OUTPUT_DIR}/beide_druckbett.stl ($(du -h "${OUTPUT_DIR}/beide_druckbett.stl" | cut -f1))${NC}"

# 4. PNG: Explosionsansicht (Steckprinzip wie im Vorlagebild)
echo -e "\n${YELLOW}▶ Rendere PNG: Explosionsansicht...${NC}"
openscad -D 'ansicht="explosion"' -o "${OUTPUT_DIR}/preview_explosion.png" "$SCAD_FILE" \
    --autocenter \
    --viewall \
    --camera=0,0,0,55,0,35,160 \
    --imgsize="$IMG_SIZE" \
    --colorscheme="$COLOR_SCHEME"
echo -e "${GREEN}✓ ${OUTPUT_DIR}/preview_explosion.png${NC}"

# 5. PNG: Zusammenbau (einsatzbereit)
echo -e "\n${YELLOW}▶ Rendere PNG: Zusammenbau...${NC}"
openscad -D 'ansicht="zusammenbau"' -o "${OUTPUT_DIR}/preview_zusammenbau.png" "$SCAD_FILE" \
    --autocenter \
    --viewall \
    --camera=0,0,0,55,0,35,140 \
    --imgsize="$IMG_SIZE" \
    --colorscheme="$COLOR_SCHEME"
echo -e "${GREEN}✓ ${OUTPUT_DIR}/preview_zusammenbau.png${NC}"

# 6. PNG: Beide Teile nebeneinander
echo -e "\n${YELLOW}▶ Rendere PNG: Einzelteile nebeneinander...${NC}"
openscad -D 'ansicht="beide"' -o "${OUTPUT_DIR}/preview_beide.png" "$SCAD_FILE" \
    --autocenter \
    --viewall \
    --camera=0,0,0,55,0,35,160 \
    --imgsize="$IMG_SIZE" \
    --colorscheme="$COLOR_SCHEME"
echo -e "${GREEN}✓ ${OUTPUT_DIR}/preview_beide.png${NC}"

# 7. PNG: Wandhalterung alleine (Führungsnut und Schraubenlöcher)
echo -e "\n${YELLOW}▶ Rendere PNG: Wandhalterung Detailansicht...${NC}"
openscad -D 'ansicht="wandhalterung"' -o "${OUTPUT_DIR}/preview_wandhalterung.png" "$SCAD_FILE" \
    --autocenter \
    --viewall \
    --camera=0,0,0,55,0,35,120 \
    --imgsize="$IMG_SIZE" \
    --colorscheme="$COLOR_SCHEME"
echo -e "${GREEN}✓ ${OUTPUT_DIR}/preview_wandhalterung.png${NC}"

# 8. STEP: build123d Export für CAD / Autodesk Fusion
if python3 -c "import build123d" &>/dev/null; then
    echo -e "\n${YELLOW}▶ Exportiere STEP-Dateien via build123d für Autodesk Fusion...${NC}"
    python3 schlauch_halteplatte_dorn.py
    echo -e "${GREEN}✓ STEP-Dateien erfolgreich exportiert.${NC}"
fi

echo -e "\n${BOLD}${GREEN}✔ Alle STLs, STEP-Dateien und Renderings erfolgreich generiert!${NC}"
