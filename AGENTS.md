# Agent Guidelines & Repository Documentation

This repository contains a parametric CAD project engineered for 3D printing (FDM) and CAD exchange (Autodesk Fusion). The project is optimized for **Agentic Coding**, providing multi-angle visual feedback, automated geometric sanity checks, and high-speed iterative workflows.

---

## 1. Project Overview & Architecture

- **Core CAD Kernel**: [`build123d`](https://github.com/gumyr/build123d) (Python wrapper around OpenCASCADE / OCCT).
- **Headless Rasterizer**: OpenSCAD (used strictly as a headless CLI renderer via stdin CSG pipes to produce STL screenshots; no `.scad` model files are maintained).
- **Core Artifacts**:
  - `build/`: Production CAD files (`.step`, `.stl`) and machine-readable `metrics.json`.
  - `preview/`: Multi-angle renderings and 4-in-1 Quad-View collages (`.png`).
- **Assemblies & Parts**:
  - **`wandhalterung`** (Wall Mount Bracket): Wall-mountable base with two recessed countersunk screw holes and an open U-channel dovetail slot.
  - **`haltehaken`** (Hose Hook Slide - Default Baseline): Detachable dovetail slider with a 5° upward-tilted stem, a 50° FDM support cone, an end collar, and a planar horizontal top face.
  - **`baugruppe_haltehaken`** (Assembly): Combined assembly in mated configuration for Autodesk Fusion.

---

## 2. Directory Structure

```text
.
├── AGENTS.md                   # This file (Agent instructions & operational guidelines)
├── schlauch_halteplatte_dorn.py # Main parametric CAD model script & CLI generator
├── generate.sh                 # Build orchestration script with fast iteration flags
├── clean.sh                    # Workspace cleanup script (--keep-step, --keep-preview)
├── .gitignore                  # Ignores build/, preview/, and temporary artifacts
├── build/                      # Generated CAD artifacts (gitignored)
│   ├── wandhalterung.step / .stl
│   ├── haltehaken.step / .stl
│   ├── baugruppe_haltehaken.step
│   └── metrics.json            # Structured geometric evaluation metrics
└── preview/                    # Generated preview images (gitignored)
    ├── haltehaken_quad.png     # 4-in-1 composite (Iso, Top, Front, Side)
    ├── wandhalterung_quad.png
    ├── zusammenbau_quad.png
    └── explosion.png           # Exploded view showing slide-in insertion path
```

---

## 3. The Agentic Iteration Loop

When modifying or verifying geometries, follow this high-velocity loop:

### Step 1: Rapid Iteration (`--fast`)
Skip the computationally heavy STEP export during geometry experimentation:
```bash
# Ultra-fast iteration on the hook only (STL + Quad-View in ~2-3 seconds):
./generate.sh --fast --part haltehaken --views quad

# Fast test on the wall bracket:
./generate.sh --fast --part wandhalterung --views quad
```

### Step 2: Validate via Terminal Metrics & JSON
Inspect the output report printed to stdout or read `build/metrics.json`:
- **Bed Contact (`bed_flat`)**: Ensure `min_z == 0.0` for print-bed adhesion.
- **Top Planarity (`top_planar`)**: Ensure the top surface normal is `[0.0, 0.0, 1.0]` (parallel to the bed) to avoid slicing terracing.
- **Dovetail Fit**: Ensure dovetail clearance (`spiel`, default 0.35 mm) is preserved.
- **Support-Free FDM**: Verify effective overhang $\le 45^\circ$ against vertical.

### Step 3: Visual Inspection via Single Quad-View Image
Instead of reading multiple image files, read the 2x2 composite quad image in one single inspection step:
- Hook: `preview/haltehaken_quad.png`
- Bracket: `preview/wandhalterung_quad.png`
- Assembly: `preview/zusammenbau_quad.png`

**Quadrant Layout in Quad-Views:**
1. **Top-Left (1. ISOMETRIC)**: 3D perspective for spatial and aesthetic inspection.
2. **Top-Right (2. TOP)**: Orthographic Z-view for dovetail fit, screw hole alignments, wall thicknesses.
3. **Bottom-Left (3. FRONT)**: Orthographic X-view for symmetry and dovetail wall angles.
4. **Bottom-Right (4. SIDE)**: Orthographic Y-profile for tilt angle (5°), base transition, and flat top.

### Step 4: Final Release Build
Once the geometry passes visual and metric checks, run a full build to generate production STEP files:
```bash
./generate.sh
```

---

## 4. CLI Reference

### `generate.sh`
Orchestrates Python build execution:

| Flag | Argument | Description | Default |
| :--- | :--- | :--- | :--- |
| `--fast`, `--no-step` | None | Skips STEP export; only generates STLs & screenshots | Off |
| `--part` | `all`, `wandhalterung`, `haltehaken`, `baugruppe` | Generates only specified part(s) | `all` |
| `--views` | `all`, `quad`, `iso`, `none` | Controls rendering output mode | `all` |
| `--json` | None | Emits structured JSON to `build/metrics.json` | Always on |
| `--spiel` | `MM` (float) | Overrides dovetail slide clearance | `0.35` |
| `--neigung` | `DEG` (float) | Overrides hook upward tilt angle | `5.0` |
| `--dorn-l` | `MM` (float) | Overrides usable hook stem length | `50.0` |
| `--dorn-d` | `MM` (float) | Overrides stem outer diameter | `16.0` |
| `--kragen-d` | `MM` (float) | Overrides end collar outer diameter | `24.0` |

### `clean.sh`
Cleans up build artifacts:

| Flag | Description |
| :--- | :--- |
| *(no args)* | Removes `build/`, `preview/`, and loose root artifacts |
| `--keep-step`, `-s` | Preserves `.step` files inside `build/` |
| `--keep-preview`, `-p` | Preserves preview screenshots inside `preview/` |

---

## 5. Engineering Constraints & Rules

1. **Pure Python CAD (`build123d`)**:
   - Do NOT introduce OpenSCAD source models (`.scad`). All CAD logic must remain in `build123d`.
   - OpenSCAD is globally installed only to render STLs into PNGs headlessly.
2. **Separate Artifacts**:
   - Never generate combined printbed STLs. Output parts separately as `wandhalterung.stl` and `haltehaken.stl`.
3. **FDM Support-Free Design Rules**:
   - The stem is tilted at 5° upward to prevent hoses/cables from sliding off.
   - The collar support cone must have a steep chamfer (default: 50° relative to the tilted axis). With 5° tilt, the overhang to vertical is $50^\circ - 5^\circ = 45^\circ$, making it 100% printable without supports.
   - The base cone transitions smoothly from a horizontal circular footprint on the slider (Z=nut_tiefe) into the 5° tilted stem.
4. **Planar Top Cut**:
   - The collar top face MUST be cut with a horizontal plane (`normal = (0, 0, 1)`) so the 3D printer finishes on a flat layer without micro-steps or slanted infill.
5. **Dovetail Sliding Tolerances**:
   - Default clearance is $0.35\text{ mm}$ on each mating face ($0.70\text{ mm}$ total width difference).
   - Bottom of dovetail channel has a 4.0 mm solid backing floor (`boden_dicke`).
