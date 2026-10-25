# Universal-Wandhalterung mit Schnellwechsel-Haltehaken

Parametrisches CAD- und 3D-Druck-Projekt für ein modulares Schwalbenschwanz-Haltesystem (z. B. für Schläuche, Kabel oder Werkzeuge). Modelliert in reinem Python mit [`build123d`](https://github.com/gumyr/build123d) für nativen STEP-CAD-Export (Autodesk Fusion) und STL-Export für den FDM-3D-Druck.

---

## Highlights & Features

- **Zweiteiliges Stecksystem**:
  - **Wandhalterung**: Robuste Basis mit zwei versenkten Senkkopf-Schraubenbohrungen und U-Kanal Schwalbenschwanzführung.
  - **Haltehaken (Baseline)**: Abnehmbarer Einschub mit 5° Aufwärtsneigung (verhindert Abrutschen) und integriertem Endkragen.
- **100% Supportfreier FDM-Druck**:
  - $50^\circ$-Stützkegel unter dem Kragen gleicht die 5°-Neigung aus (effektiver Überhang $\le 45^\circ$).
  - Die Deckfläche ist horizontal planparallel zum Druckbett geschnitten (keine Stufenbildung im Slicer).
- **Multi-View Visualisierung**: Automatische 4-in-1 Quad-View Renderings (Iso, Top, Front, Side) via Headless-Rasterizer.

---

## Schnellstart

### Voraussetzungen
- Python 3.10+
- `build123d` und `Pillow`
- `openscad` (optional, für automatische Vorschau-Renderings)

```bash
pip install build123d pillow
```

### Build ausführen
```bash
# Standard-Build: STEP für Fusion, STL für 3D-Druck und alle Renderings
./generate.sh

# Schneller Testlauf (nur STLs & Quad-Views in ~2-3s):
./generate.sh --fast

# Nur den Haltehaken generieren:
./generate.sh --fast --part haltehaken --views quad

# Bereinigung:
./clean.sh
```

---

## Verzeichnisstruktur

- [`schlauch_halteplatte_dorn.py`](schlauch_halteplatte_dorn.py): Hauptmodell & parametrischer CAD-Generator.
- [`generate.sh`](generate.sh): Build-Orchestrierung mit CLI-Parametrisierung (`--spiel`, `--neigung`, `--fast`).
- [`clean.sh`](clean.sh): Bereinigungsskript (`--keep-step`, `--keep-preview`).
- `build/`: Generierte `.step`, `.stl` und `metrics.json`.
- `preview/`: Generierte Renderings und Quad-View Collagen (`.png`).
- [`AGENTS.md`](AGENTS.md): Detaillierte Entwicklungs- und Iterationsrichtlinien für KI-Agenten.
