---
name: new-project
description: >-
  Use this skill when the user wants to start or scaffold a new CAD / 3D printing
  project in the projects/ directory based on the repository template.
---

# New CAD Project Workflow

Use this skill to bootstrap a new parametric `build123d` CAD project from `template/`, capture its requirements in `SPEC.md`, implement the initial geometry in `model.py`, verify it visually and numerically, and hand off to the user for iterative refinement.

Follow [`AGENTS.md`](../../../AGENTS.md) for all `build123d` modeling rules, FDM printability constraints, and CLI conventions.

---

## Step 1: Gather Requirements

Before creating files, review what the user already told you and ask focused clarifying questions (using `ask_question` when choices or missing specs remain) to establish:

1. **Project Slug & Location**: Lowercase snake_case folder name under `projects/<project_slug>/`.
2. **Purpose & Parts Breakdown**: What the object does, whether it is a single part or multi-part assembly, and the part names.
3. **Key Dimensions & Hardware**: Overall envelope (`width`, `length`, `height`), mounting/fastener standards (e.g., M3/M4/M5 clearance or countersink holes), and mating clearances (e.g., `0.25–0.40 mm` for sliding fits).
4. **Print Orientation & Constraints**: Print-bed contact face (`Z = 0`), support-free overhang limit ($\le 45^\circ$), load direction, and whether a flat horizontal top cut is needed.

If the user already supplied enough detail for a sensible baseline, state any reasonable engineering defaults explicitly rather than stalling on trivial questions.

---

## Step 2: Scaffold from `template/`

Copy `template/` into `projects/<project_slug>/` and verify permissions:

```bash
cp -r template projects/<project_slug>
chmod +x projects/<project_slug>/generate.sh projects/<project_slug>/clean.sh projects/<project_slug>/model.py
```

Ensure `generate.sh` and `clean.sh` remain generic wrappers (do not hardcode project-specific `--help` text inside `generate.sh`; it delegates `--help` to `model.py`).

---

## Step 3: Write Initial `SPEC.md` and `README.md`

1. Populate `projects/<project_slug>/SPEC.md` using the declarative structure from `template/SPEC.md`:
   - **Overview & Purpose**
   - **Parts & Assembly Architecture** (part names, output `.stl`/`.step` files, roles)
   - **Parametric Dimensions & Configuration** (every `Config` field, default value, CLI flag, and `@property` derivation)
   - **Functional & FDM Printability Constraints**
   - **Verification & Acceptance Criteria** (expected bounding boxes, `bed_flat == true`, overhang/clearance targets)
2. Update `projects/<project_slug>/README.md` with the project title, feature summary, and `./generate.sh` examples using the project's actual `--part` names and parameter flags.

---

## Step 4: Implement Initial Geometry in `projects/<project_slug>/model.py`

Implement the project in `model.py` following the `build123d` standards in `AGENTS.md`:

- Define primary dimensions on the `Config` dataclass and derived geometry as `@property` methods.
- Build parts using 2D-before-3D BREP workflows (`BuildPart` $\rightarrow$ `BuildSketch` $\rightarrow$ `extrude` / `loft` / `revolve`), native holes (`Hole`, `CounterSinkHole`), and `split()` instead of OpenSCAD-style CSG cutting boxes.
- Keep `analyze_part_geometry`, `print_metrics_report` (customized with project-specific fit/overhang checks), and the OpenSCAD + Pillow rendering pipeline intact.
- For multi-part assemblies, export each printable part as its own `.stl` and `.step`, and use `copy.copy(part).move(...)` inside `Compound(...)` for `build/assembly.step` plus `assembly` / `exploded` preview renders.
- Expose `--part` choices and key dimension overrides on `argparse`.

---

## Step 5: Build & Verify Initial Implementation

Run the fast iteration loop first inside `projects/<project_slug>/`:

```bash
cd projects/<project_slug>
./generate.sh --fast --views quad
```

1. Inspect `build/metrics.json` and stdout metrics:
   - Verify `bed_flat == true` (`min_z == 0.0`) for all printable parts.
   - Verify `top_planar == true` where flat top surfaces are specified.
   - Verify bounding-box dimensions and clearances match `SPEC.md`.
2. Visually inspect each generated `preview/*_quad.png` using `read_file` across all 4 quadrants (Isometric, Top, Front, Side).
3. Fix any geometric or printability issues (and update `SPEC.md` if any design adjustments were made), then run a full release build:
   ```bash
   ./generate.sh
   ```

---

## Step 6: Hand Off to the Synchronized Iteration Loop

Present a concise summary to the user with:
- Links to `projects/<project_slug>/SPEC.md`, `model.py`, and key `preview/*_quad.png` files.
- Verified dimensions and sanity check results from `build/metrics.json`.
- A prompt inviting the user to request adjustments (any future changes must keep `SPEC.md` and `model.py` synchronized per `AGENTS.md`).
