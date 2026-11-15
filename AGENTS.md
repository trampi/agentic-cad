# Agent Guidelines & Repository Documentation

This repository hosts a generalized **Parametric CAD & 3D-Printing Harness** engineered for **FDM 3D printing** and **CAD exchange (Autodesk Fusion)** across multiple independent projects. The workflow is optimized for **Agentic Coding**, combining living specifications (`SPEC.md`), automated geometric sanity checks (`metrics.json`), multi-angle visual feedback (Quad-View collages), and high-speed iterative loops.

---

## 1. Workspace Overview & Architecture

- **Core CAD Kernel**: [`build123d`](https://github.com/gumyr/build123d) (Python wrapper around OpenCASCADE / OCCT).
- **Headless Rasterizer**: OpenSCAD (used strictly as a headless CLI renderer via stdin CSG pipes to produce STL screenshots; no `.scad` model files are maintained).
- **Multi-Project Structure**:
  - `template/`: Canonical starter harness (`generate.sh`, `clean.sh`, `model.py`, `SPEC.md`, `README.md`) copied into every new project.
  - `projects/<project_name>/`: Self-contained CAD projects, each owning its own scripts (`generate.sh`, `clean.sh`), `SPEC.md`, `README.md`, `model.py`, `build/`, and `preview/`.
  - `.agents/skills/new-project/`: Workspace skill for bootstrapping a new CAD project from `template/` and user requirements.
- **Concrete Reference Project (`projects/hose_hook/`)**:
  - **`wall_mount`**: Wall-mountable bracket with two recessed M4 countersunk screw holes and an open-top U-channel dovetail slot.
  - **`hose_hook`** (Default Baseline): Detachable dovetail slider with a $5^\circ$ upward-tilted stem, a $50^\circ$ FDM support cone, an end collar, and a planar horizontal top face.
  - **`assembly`**: Combined assembly in mated configuration (`Assembly_HoseHook`) for Autodesk Fusion.

---

## 2. Directory Structure

```text
.
├── AGENTS.md                        # Workspace-wide agent instructions & CAD standards
├── README.md                        # Repository overview, prerequisites & project index
├── .gitignore                       # Ignores **/build/, **/preview/, and Python caches
├── .agents/
│   └── skills/
│       └── new-project/
│           └── SKILL.md             # Skill to scaffold & implement new CAD projects
├── template/                        # Canonical per-project template
│   ├── generate.sh                  # Generic build wrapper delegating to model.py
│   ├── clean.sh                     # Artifact cleanup script (--keep-step, --keep-preview)
│   ├── model.py                     # Starter build123d model + metrics + rendering harness
│   ├── SPEC.md                      # Living specification template
│   └── README.md                    # Project README template
└── projects/
    └── hose_hook/                   # Concrete reference project (Wall Mount + Hose Hook)
        ├── generate.sh
        ├── clean.sh
        ├── model.py                 # Parametric wall_mount, hose_hook & assembly generator
        ├── SPEC.md                  # Living specification synchronized with requirements
        ├── README.md
        ├── build/                   # Generated CAD artifacts (.step, .stl, metrics.json)
        └── preview/                 # Generated renderings (*_quad.png, single views, exploded.png)
```

---

## 3. The `SPEC.md`-Synchronized Agentic Iteration Loop

All CAD builds and iterations happen **inside a specific project directory** (`cd projects/<project_name>`). Every project maintains a `SPEC.md` file that acts as the **single source of truth** between user requirements and the Python CAD implementation.

### Step 0: Synchronize `SPEC.md` with User Requirements
Before editing `model.py`, review `projects/<project_name>/SPEC.md`:
- Record any new or modified user requirements (functional goals, part breakdown, dimensions, mating clearances, fastener sizes, print orientation, or overhang limits).
- Keep the Parametric Dimensions table, Derived Properties, and Verification Criteria in `SPEC.md` up to date so they accurately describe the intended geometry.

### Step 1: Rapid Iteration (`--fast`)
Skip the computationally heavy STEP export while experimenting with geometry:
```bash
cd projects/hose_hook

# Ultra-fast iteration on a single part (STL + Quad-View in ~2-3 seconds):
./generate.sh --fast --part hose_hook --views quad

# Fast test on another part or full assembly:
./generate.sh --fast --part wall_mount --views quad
```

### Step 2: Validate via Terminal Metrics & `metrics.json`
Inspect the terminal report and `build/metrics.json` against the acceptance criteria in `SPEC.md`:
- **Bed Contact (`bed_flat`)**: Ensure `min_z == 0.0` and bottom normal is `(0, 0, -1)` for print-bed adhesion.
- **Top Planarity (`top_planar`)**: Where flat top layers are required, verify `top_normal == [0.0, 0.0, 1.0]` to avoid slicing terracing.
- **Bounding Box & Tolerances**: Confirm `bbox` dimensions, clearances (e.g., `clearance = 0.35 mm`), and overhang angles (e.g., effective overhang $\le 45^\circ$ from vertical) match `SPEC.md`.

### Step 3: Visual Inspection via Single Quad-View Image
Inspect the 2x2 composite Quad-View image instead of reading four separate screenshots:
- Reference example (`projects/hose_hook/`):
  - `preview/hose_hook_quad.png`
  - `preview/wall_mount_quad.png`
  - `preview/assembly_quad.png`

**Quadrant Layout in Quad-Views:**
1. **Top-Left (1. ISOMETRIC)**: 3D perspective for spatial and aesthetic inspection.
2. **Top-Right (2. TOP)**: Orthographic Z-view for mating fit, hole alignment, and wall thicknesses.
3. **Bottom-Left (3. FRONT)**: Orthographic X-view for symmetry and draft/dovetail angles.
4. **Bottom-Right (4. SIDE)**: Orthographic Y-profile for tilt angles, base transitions, and flat top surfaces.

### Step 4: Final Release Build & Spec Sign-Off
Once visual and metric checks pass, run a full build inside the project directory to generate production STEP files:
```bash
./generate.sh
```
Verify that `SPEC.md`, `model.py`, and `build/metrics.json` agree completely before finishing.

---

## 4. Per-Project CLI Reference

Each project contains copies of `generate.sh` and `clean.sh` from `template/`.

### `generate.sh`
`generate.sh` is generic and forwards all options (including `--help`) directly to the project's `model.py`. Standard harness flags implemented across projects:

| Flag | Argument | Description | Default |
| :--- | :--- | :--- | :--- |
| `--fast`, `--no-step` | None | Skips STEP export; only generates STLs & previews | Off |
| `--part` | Project-defined (e.g. `all`, `wall_mount`, `hose_hook`, `assembly`) | Generates only specified part(s) | `all` |
| `--views` | `all`, `quad`, `iso`, `none` | Controls rendering output mode | `all` |
| `--json` | None | Emits structured JSON to `build/metrics.json` | Always on |
| `--build-dir` | `DIR` | Output directory for CAD artifacts | `build` |
| `--preview-dir` | `DIR` | Output directory for preview images | `preview` |

Project-specific parameter flags are exposed by each project's `model.py` (run `./generate.sh --help`). For example, in `projects/hose_hook/`:
- `--clearance MM` (default: `0.35`)
- `--tilt DEG` (default: `-5.0`)
- `--stem-length MM` / `--stem-l MM` (default: `50.0`)
- `--stem-diameter MM` / `--stem-d MM` (default: `16.0`)
- `--collar-diameter MM` / `--collar-d MM` (default: `24.0`)

### `clean.sh`
Cleans up build artifacts in the current project directory:

| Flag | Description |
| :--- | :--- |
| *(no args)* | Removes `build/`, `preview/`, `__pycache__/`, and loose root artifacts |
| `--keep-step`, `-s` | Preserves `.step`/`.stp` files inside `build/` |
| `--keep-preview`, `-p` | Preserves preview screenshots inside `preview/` |

---

## 5. `build123d` Best Practices & CAD Modeling Rules

All CAD geometry in every project's `model.py` follows idiomatic **BREP modeling (`build123d` Builder mode)** rather than OpenSCAD-style 3D CSG boolean chains:

1. **2D before 3D (`BuildPart` $\rightarrow$ `BuildSketch` $\rightarrow$ `extrude` / `loft` / `revolve`)**:
   - Prefer 2D sketches and 2D fillets (`RectangleRounded`, `_draw_dovetail_u_profile`) before extruding or lofting into 3D.
   - Bound 2D profiles to their exact target dimensions in the sketch (e.g., terminating the dovetail slider sketch at `cfg.y_top` in `projects/hose_hook/model.py`) rather than lofting oversized shapes and trimming them with 3D cutting boxes.
   - Model axisymmetric features (such as the stem, $50^\circ$ support cone, collar, or hose barbs) as a single 2D half-profile (`BuildSketch` $\rightarrow$ `BuildLine` $\rightarrow$ `Polyline` $\rightarrow$ `make_face()`) and revolve $360^\circ$ via `revolve(axis=...)` instead of unioning stacked `Cylinder` and `Cone` primitives.

2. **Nested Builder Coordinate Systems & Placements**:
   - Every `BuildSketch` constructs geometry in its own local `Plane.XY` coordinate system and only transforms to its target `Plane` when exiting the context block.
   - When nesting `BuildLine` inside `BuildSketch`, **always use the default `BuildLine()` placement (`Plane.XY`)**. Passing a non-XY plane to `BuildLine` inside `BuildSketch` causes an unintended placement-and-reprojection round-trip.
   - Builders do **not** inherit placements from parent builders; pass explicit `Plane` or `Location` contexts where needed.
   - Note that `BuildSketch` checks its immediate caller frame to register with an enclosing `BuildPart`. Shared 2D helper functions (like `_draw_dovetail_u_profile`) should emit 2D primitives inside an active `with BuildSketch(...):` block in `BuildPart`.

3. **No OpenSCAD CSG Hacks (`Box` Cutters or $+0.05\text{ mm}$ Epsilons)**:
   - **Planar Bisection**: Use `split(bisect_by=Plane.XY.offset(...), keep=Keep.BOTTOM)` to cut solids with an infinite mathematical plane instead of subtracting hardcoded `Box(200, 200, 100)` solids that can fail when parameters scale up.
   - **Coplanar Lofts**: Do not add $+0.05\text{ mm}$ Z-fighting offsets to loft planes (which distorts taper angles). Sketch directly on the target face (`bracket_bp.faces().sort_by(Axis.Z)[-1]`) or exact offset plane with `loft(mode=Mode.SUBTRACT)`.

4. **Native Hole Features & Instancing (`Locations`, `CounterSinkHole`, `Hole`)**:
   - Use `CounterSinkHole` and `Hole` combined with `Locations((x1, y1), (x2, y2))` to instance hole features across multiple coordinates rather than manually uniting and subtracting cylinders and cones.

5. **Parameterization (`Config` Dataclass, `@property` Derivations & Web Metadata)**:
   - Store primary dimensions as fields on `Config` and define dependent geometric values (e.g., `slot_depth`, `y_top`, `y_u_center`, `slider_width_back`, `slider_width_front`, `y_stem`, `effective_overhang_angle` in `projects/hose_hook/model.py`) as `@property` methods.
   - Annotate tunable `Config` fields with `dataclasses.field(metadata={"label": ..., "min": ..., "max": ..., "step": ..., "unit": ..., "group": ...})` (or `"choices"` / `bool`) and expose `build_web_parts(cfg)` so `scripts/build_site.py` and the static Pyodide/`OCP.wasm` customizer (`web/`) work automatically for every project.
   - Keep `Pillow` (`PIL`) imports lazy inside CLI/collage rendering helpers (`build_quad_collage`) so `model.py` imports cleanly inside browser Pyodide without extra image dependencies.
   - Because `dataclasses.asdict(cfg)` serializes only dataclass fields (ignoring `@property` methods), derived formulas stay centralized in `Config` without polluting `build/metrics.json`.

6. **Shallow Copies in Assemblies (`copy.copy`)**:
   - When positioning parts for assemblies (`Compound`), use `copy.copy(part).move(Location(...))` instead of `Pos(...) * part`. `Pos(...) * part` invokes `copy.deepcopy()`, duplicating the underlying OpenCASCADE `TopoDS_TShape`, whereas `copy.copy()` shares the `TopoDS_TShape` reference.

7. **Topology Object Selection**:
   - Use `build123d` topology selectors (`solid.faces().sort_by(Axis.Z)[0]`, `solid.faces().sort_by(Axis.Z)[-1]`, `face.geom_type == GeomType.PLANE`, and `face.normal_at()`) rather than manual coordinate list comprehensions.

---

## 6. Engineering Constraints, FDM Printability & CAD Exchange

1. **Pure Python CAD (`build123d`)**:
   - Do NOT introduce OpenSCAD source models (`.scad`). All CAD logic must remain in `build123d`.
   - OpenSCAD is used strictly headlessly to rasterize STLs into PNGs.
2. **Separate Printable Artifacts**:
   - Never generate combined print-bed STLs. Export each printable part as its own `.stl` file (e.g., `wall_mount.stl` and `hose_hook.stl`) and combine parts only in assembly STEP exports (`assembly.step`) and preview renderings.
3. **FDM Support-Free Design Rules**:
   - Orient parts so their largest flat surface rests on `Z = 0` (`bed_flat == true`).
   - Keep unsupported overhangs $\le 45^\circ$ from vertical (in `projects/hose_hook/`, the $50^\circ$ collar chamfer compensates for the $5^\circ$ upward stem tilt: $50^\circ - 5^\circ = 45^\circ$).
   - Transition tilted features smoothly from horizontal slider surfaces via `loft()`.
4. **Planar Top Cuts**:
   - Where a tilted feature ends near the top, bisect it with a horizontal plane (`Plane.XY.offset(...)`, `normal = (0, 0, 1)`) via `split()` so the 3D printer finishes cleanly without micro-steps.
5. **Tolerances & Clearances**:
   - Parameterize mating clearances explicitly in `Config` (e.g., `clearance = 0.35 mm` per side on dovetails) and document them in `SPEC.md`.
6. **Autodesk Fusion STEP Exchange**:
   - Standard STEP (`AP214`) exports exact analytical B-Rep surfaces (`PLANE`, `CYLINDRICAL_SURFACE`, `CONICAL_SURFACE`) and assembly hierarchy (`Compound`).
   - Preserving clean analytical surfaces (via `revolve`, `extrude`, `CounterSinkHole`, and `split`) allows Autodesk Fusion's **Find Features** and **Press Pull** tools to recognize cylinders, cones, holes, and fillets after STEP import.

---

## 7. Creating a New Project

To start a new parametric CAD project:
1. Use the **`new-project`** skill (`.agents/skills/new-project/SKILL.md`), which guides requirement gathering, copies `template/` to `projects/<project_name>/`, authors the initial `SPEC.md`, implements `model.py`, runs verification (`--fast --views quad` followed by `./generate.sh`), and hands off into the `SPEC.md`-synchronized iteration loop.
2. Or manually copy `template/` into `projects/<project_name>/`, customize `SPEC.md`, `README.md`, and `model.py`, and run `./generate.sh`.
