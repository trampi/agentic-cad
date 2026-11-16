# Universal Wall Mount & Quick-Release Hose Hook

Parametric CAD and 3D-printing project for a modular dovetail mounting system (e.g., for hoses, cables, or tools). Modeled in pure Python using [`build123d`](https://github.com/gumyr/build123d) for native STEP export (Autodesk Fusion) and STL export for FDM 3D printing.

---

## Highlights & Features

- **Two-Piece Quick-Release System**:
  - **Wall Mount (`wall_mount`)**: Sturdy bracket with two recessed M4 countersunk screw holes and an open-top U-channel dovetail slot.
  - **Hose Hook (`hose_hook`, baseline)**: Detachable slider with a $5^\circ$ upward-tilted stem (prevents slipping) and an integrated retention collar.
- **100% Support-Free FDM Printing**:
  - A $50^\circ$ support cone beneath the collar compensates for the $5^\circ$ tilt (effective overhang $\le 45^\circ$).
  - The top face is sliced horizontally parallel to the print bed (no stair-stepped top layers in the slicer).
- **Multi-View Visualization**: Automated 4-in-1 Quad-View contact sheets (Iso, Top, Front, Side) and exploded assembly view via headless OpenSCAD.

---

## Quickstart

```bash
# Full release build: STEP for Fusion, STL for 3D printing, metrics.json & all previews
./generate.sh

# Fast iteration (STLs & Quad-Views in ~2-3s, skips STEP export)
./generate.sh --fast

# Build only the hose hook with Quad-View preview
./generate.sh --fast --part hose_hook --views quad

# Override parametric clearance or stem length
./generate.sh --fast --clearance 0.30 --stem-length 60.0

# Clean generated artifacts
./clean.sh
```

---

## Project Files

- [`SPEC.md`](SPEC.md): Living specification synchronized with requirements, dimensions, and verification criteria.
- [`model.py`](model.py): Main parametric CAD model and verification harness.
- [`generate.sh`](generate.sh): Build wrapper forwarding CLI flags to `model.py`.
- [`clean.sh`](clean.sh): Cleanup script (`--keep-step`, `--keep-preview`).
- [`photos/`](photos/): Real-life photos of the printed & installed pieces (`captions.json` for descriptions).
- `build/`: Generated `.step`, `.stl`, and `metrics.json`.
- `preview/`: Generated renderings and Quad-View collages `.png`.
