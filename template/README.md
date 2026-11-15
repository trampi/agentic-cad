# `<Project Name>`

Parametric CAD and 3D-printing project modeled in pure Python using [`build123d`](https://github.com/gumyr/build123d) for native STEP export (Autodesk Fusion) and STL export for FDM 3D printing.

---

## Quickstart

### Prerequisites
- Python 3.10+
- `build123d` and `Pillow`
- `openscad` (optional, for automated multi-view preview renderings)

### Build Commands
```bash
# Full release build (STEP, STL, metrics.json, and all preview renderings)
./generate.sh

# Fast iteration build (STLs, metrics.json, and Quad-View previews only)
./generate.sh --fast --views quad

# Show all project-specific CLI options & parts
./generate.sh --help

# Clean generated artifacts
./clean.sh

# Preview in the static web gallery & 3D customizer (from repo root)
python3 ../../scripts/build_site.py --out ../../_site --serve
```

---

## Project Files

- [`SPEC.md`](SPEC.md): Living specification synchronized with user requirements, dimensions, and verification criteria.
- [`model.py`](model.py): Main parametric `build123d` CAD model and verification harness.
- [`generate.sh`](generate.sh): Project build wrapper forwarding options to `model.py`.
- [`clean.sh`](clean.sh): Cleanup script (`--keep-step`, `--keep-preview`).
- `build/`: Generated `.step`, `.stl`, and `metrics.json` (gitignored).
- `preview/`: Generated renderings and 2x2 Quad-View collages `.png` (gitignored).
