# Sculptural 4-Slot Couch-Table Remote Stand

Parametric CAD and 3D-printing project for a compact, support-free 4-slot stepped remote holder (Light, Amazon Fire TV, LG, and Bose 3-2-1 remotes) resting on their side edge at a $30^\circ$ angle. Modeled in pure Python using [`build123d`](https://github.com/gumyr/build123d) for native STEP export (Autodesk Fusion) and STL export for FDM 3D printing.

---

## Highlights & Features

- **4 Staggered Stepped $30^\circ$ Cradles (Front to Back)**:
  - **Slot 1**: Small Light remote (`20 mm` slot, `92 mm` cradle width)
  - **Slot 2**: Amazon Fire TV remote (`20 mm` slot, `105 mm` cradle width)
  - **Slot 3**: LG TV remote (`35 mm` slot, `128 mm` cradle width)
  - **Slot 4**: Bose 3-2-1 series remote (`36 mm` slot, `172 mm` cradle width)
- **Space-Saving Open-Ended Design**: Centered staggered cradles (~75% of each remote's width) widen proportionally from front to back while leaving ends open to grab easily.
- **Sculptural Wave & Stepped Twin-Rail Pickup Canyon**: Rounded outer corners per tier, filleted wave crests/troughs, and a deep stepped central pickup channel (`60 / 73 / 96 / 140 mm` wide, keeping uniform `16 mm` support rails per side over a thin `2.4 mm` flat base floor) to save filament while giving effortless two-finger grabbing.
- **100% Support-Free FDM Printing**: Prints flat on `Z = 0` with $30^\circ$ maximum wall inclinations and a planar horizontal top crest.

---

## Quickstart

```bash
# Full release build: STEP for Fusion, STL for 3D printing, metrics.json & all previews
./generate.sh

# Fast iteration (STLs & Quad-Views only, skips STEP export)
./generate.sh --fast --views quad

# Build only the printable stand (without remote bounding boxes)
./generate.sh --fast --part remote_stand --views quad

# Build assembly showcase without or with optional remote bounding boxes
./generate.sh --fast --part assembly --no-remote-boxes
./generate.sh --fast --part remote_boxes --views quad

# Customize tier widths, slot widths, or tilt angle
./generate.sh --fast --tier4-width 185.0 --tilt 28.0 --slot3-width 32.0

# Clean generated artifacts
./clean.sh
```

---

## Project Files

- [`SPEC.md`](SPEC.md): Living specification synchronized with requirements, dimensions, and verification criteria.
- [`model.py`](model.py): Main parametric `build123d` CAD model and verification harness.
- [`generate.sh`](generate.sh): Build wrapper forwarding CLI flags to `model.py`.
- [`clean.sh`](clean.sh): Cleanup script (`--keep-step`, `--keep-preview`).
- `build/`: Generated `.step`, `.stl`, and `metrics.json` (gitignored).
- `preview/`: Generated renderings and Quad-View collages `.png` (gitignored).
