# Project Specification: Universal Wall Mount & Quick-Release Hose Hook

> **Living Specification**: Keep this document synchronized with all user requirements, parametric dimensions, design constraints, and verification criteria before and after every CAD iteration.

---

## 1. Overview & Purpose

A modular two-piece quick-release dovetail mounting system engineered for support-free FDM 3D printing and Autodesk Fusion STEP exchange. A wall-mounted bracket accepts a detachable slider carrying an upward-tilted hook stem with a retention collar (e.g., for hoses, cables, or workshop tools), or optionally a barbed mandrel (`hose_barb`).

---

## 2. Parts & Assembly Architecture

| Part / Assembly | Output Files | Role & Key Features |
| :--- | :--- | :--- |
| `wall_mount` | `build/wall_mount.stl`, `build/wall_mount.step` | Wall-mountable plate with rounded corners, open-top U-channel dovetail slot, and two recessed M4 countersunk screw holes. |
| `hose_hook` | `build/hose_hook.stl`, `build/hose_hook.step` | Detachable dovetail slider with a $5^\circ$ upward-tilted cylindrical stem, base transition cone, $50^\circ$ FDM support cone, end collar, and planar horizontal top face. |
| `assembly` | `build/assembly.step` | Combined `Compound` (`Assembly_HoseHook`) with `hose_hook` mated inside `wall_mount` at $Z = \text{back\_wall\_thickness}$ (`4.0 mm`). |

---

## 3. Parametric Dimensions & Configuration

All primary parameters are defined in `Config` inside `model.py`.

### Mode & Wall Mount Bracket

| Parameter | `Config` Field | Default | CLI Flag | Description |
| :--- | :--- | :--- | :--- | :--- |
| Stem Variant | `stem_type` | `"hose_hook"` | — | `"hose_hook"` (baseline) or `"hose_barb"` |
| Bracket Width | `bracket_width` | `50.0 mm` | — | Overall bracket X width |
| Bracket Height | `bracket_height` | `70.0 mm` | — | Overall bracket Y height |
| Bracket Depth | `bracket_depth` | `12.0 mm` | — | Overall bracket Z thickness |
| Back Wall Thickness | `back_wall_thickness` | `4.0 mm` | — | Solid floor thickness behind dovetail slot |
| Corner Radius | `corner_radius` | `4.0 mm` | — | Outer corner fillet radius |
| Bottom Margin | `bottom_margin` | `4.0 mm` | — | Wall thickness below the U-channel semicircle |

### Dovetail Guide & Fasteners

| Parameter | `Config` Field | Default | CLI Flag | Description |
| :--- | :--- | :--- | :--- | :--- |
| Slot Width (Back) | `slot_width_back` | `36.0 mm` | — | Dovetail slot width at channel floor |
| Slot Width (Front) | `slot_width_front` | `30.0 mm` | — | Dovetail slot width at front surface |
| Sliding Clearance | `clearance` | `0.35 mm` | `--clearance` | Bilateral mating clearance per side (`0.70 mm` total width difference) |
| Screw Shaft Diameter | `screw_diameter` | `4.4 mm` | — | M4 clearance hole diameter |
| Countersink Diameter | `countersink_diameter` | `8.7 mm` | — | M4 countersink head diameter |
| Countersink Angle | `countersink_angle` | `90.0°` | — | Nominal countersink cone angle |
| Top Screw Y | `screw_top_y` | `16.0 mm` | — | Upper screw hole Y coordinate |
| Bottom Screw Y | `screw_bottom_y` | `-14.0 mm` | — | Lower screw hole Y coordinate |

### Hook Stem, Collar & Optional Barbs

| Parameter | `Config` Field | Default | CLI Flag | Description |
| :--- | :--- | :--- | :--- | :--- |
| Stem Diameter | `stem_diameter` | `16.0 mm` | `--stem-diameter`, `--stem-d` | Cylindrical stem outer diameter |
| Stem Length | `stem_length` | `50.0 mm` | `--stem-length`, `--stem-l` | Usable stem length along tilted axis |
| Stem Tilt | `stem_tilt` | `-5.0°` | `--tilt` | Upward tilt rotation around X axis |
| Base Chamfer | `base_chamfer` | `5.0 mm` | — | Base transition cone radial margin & height |
| Inner Bore | `inner_bore` | `0.0 mm` | — | Optional through-bore along stem (`0` = solid) |
| Stem Y Factor | `stem_y_factor` | `0.42` | — | Relative Y placement on slider between `y_u_center` and `y_top` |
| Collar Diameter | `collar_diameter` | `24.0 mm` | `--collar-diameter`, `--collar-d` | End retention collar outer diameter |
| Collar Thickness | `collar_thickness` | `4.0 mm` | — | End collar axial thickness |
| Collar Chamfer Angle | `collar_chamfer_angle` | `50.0°` | — | Support cone angle relative to stem axis |
| Barb Count | `barb_count` | `3` | — | Number of retention barbs (`hose_barb` mode) |
| Barb Height | `barb_height` | `1.2 mm` | — | Radial barb protrusion (`hose_barb` mode) |
| Barb Length | `barb_length` | `7.0 mm` | — | Axial length per barb (`hose_barb` mode) |
| Tip Chamfer | `tip_chamfer` | `4.0 mm` | — | Lead-in tip chamfer (`hose_barb` mode) |

### Derived Properties (`@property` on `Config`)
- `slot_depth`: `bracket_depth - back_wall_thickness` (`8.0 mm`)
- `y_top`: `bracket_height / 2.0` (`35.0 mm`)
- `y_u_center`: `-bracket_height / 2.0 + slot_width_back / 2.0 + bottom_margin` (`-13.0 mm`)
- `slider_width_back`: `slot_width_back - 2.0 * clearance` (`35.3 mm`)
- `slider_width_front`: `slot_width_front - 2.0 * clearance` (`29.3 mm`)
- `y_stem`: `y_u_center + (y_top - y_u_center) * stem_y_factor` (`7.16 mm`)
- `effective_overhang_angle`: `collar_chamfer_angle - abs(stem_tilt)` (`45.0°`)

---

## 4. Functional & FDM Printability Constraints

1. **Print-Bed Adhesion**: Both `wall_mount` and `hose_hook` must print flat with `min_z == 0.0 mm` (`bed_flat == true`), printed as separate STL artifacts (`wall_mount.stl` and `hose_hook.stl`).
2. **Support-Free FDM Overhangs**:
   - The $5^\circ$ upward tilt prevents hoses or cables from sliding off.
   - The $50^\circ$ support cone beneath the end collar compensates for the $5^\circ$ tilt, yielding an effective overhang of $45^\circ$ from vertical (`effective_overhang_angle <= 45.0°`).
   - A `loft()` base cone transitions smoothly from a horizontal circular footprint on the slider top (`Z = slot_depth`) into the tilted stem.
3. **Planar Horizontal Top Face**: The collar top face is bisected with `Plane.XY.offset(z_top_plane)` (`top_normal == [0.0, 0.0, 1.0]`, `top_planar == true`) so the printer finishes on a clean flat layer without stepped terracing.
4. **Dovetail Fit**: Default sliding clearance is `0.35 mm` on each mating face (`0.70 mm` total width difference), backed by a `4.0 mm` solid floor (`back_wall_thickness`).
5. **Autodesk Fusion STEP Compatibility**: Clean analytical B-Rep surfaces (`PLANE`, `CYLINDRICAL_SURFACE`, `CONICAL_SURFACE`) and `Compound` assembly hierarchy exported as STEP (`AP214`).

---

## 5. Verification & Acceptance Criteria

- **Automated Metrics (`build/metrics.json`)**:
  - `wall_mount`: `size_x == 50.0`, `size_y == 70.0`, `size_z == 12.0`, `min_z == 0.0`, `bed_flat == true`, `top_planar == true`.
  - `hose_hook`: `size_x == 35.3`, `size_y == 65.65`, `size_z == 58.86`, `min_z == 0.0`, `bed_flat == true`, `top_planar == true`.
- **Visual Inspection (`preview/*_quad.png` & `preview/exploded.png`)**:
  - `wall_mount_quad.png`: Clean U-channel dovetail slot and recessed countersunk holes aligned on `X = 0`.
  - `hose_hook_quad.png`: Smooth base loft transition, $5^\circ$ upward tilt in Side view, $50^\circ$ collar support cone, and horizontal top plane.
  - `assembly_quad.png` & `exploded.png`: Proper dovetail engagement and insertion path along Y.
