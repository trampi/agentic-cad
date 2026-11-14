#!/usr/bin/env bash
# ====================================================================
# CAD Build Script (Python / build123d) - Optimized for Agentic Coding
# Generates:
#   - build/   : STEP files (Autodesk Fusion), STL files & metrics.json
#   - preview/ : Multi-view renderings (Iso, Top, Front, Side, Quad collage)
# ====================================================================

set -euo pipefail

GREEN="\033[0;32m"
BLUE="\033[0;34m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
BOLD="\033[1m"
NC="\033[0m"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY_SCRIPT="${SCRIPT_DIR}/model.py"

if [[ ! -f "$PY_SCRIPT" ]]; then
    echo -e "${RED}[Error] Entrypoint not found: ${PY_SCRIPT}${NC}" >&2
    exit 1
fi

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}[Error] python3 is not installed.${NC}" >&2
    exit 1
fi

# Delegate --help / -h directly to model.py so project-specific flags & parts appear
for arg in "$@"; do
    if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
        echo -e "${BOLD}${BLUE}Usage:${NC} $0 [OPTIONS]"
        echo ""
        echo "All options are forwarded to model.py:"
        echo ""
        python3 "$PY_SCRIPT" --help
        exit 0
    fi
done

# Check build123d
if ! python3 -c "import build123d" &>/dev/null; then
    echo -e "${RED}[Error] build123d is not installed.${NC}" >&2
    echo "Install it with: pip install build123d" >&2
    exit 1
fi

echo -e "${BOLD}${BLUE}=== Starting CAD Build (build123d / Python) ===${NC}"

python3 "$PY_SCRIPT" "$@"

echo -e "\n${BOLD}${GREEN}✔ Done! Artifacts are in 'build/' and 'preview/'${NC}"
