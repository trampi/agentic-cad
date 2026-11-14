# Project Specification: Sculptural 4-Slot Couch-Table Remote Stand

> **Living Specification**: Keep this document synchronized with all user requirements, parametric dimensions, design constraints, and verification criteria before and after every CAD iteration.

---

## 1. Overview & Purpose

A compact, sculptural 4-slot stepped couch-table stand for 4 TV/media remotes lying lengthwise (left-to-right along `X`) on their side edge at a $30^\circ$ backward tilt (`tilt_angle = 30.0°` from vertical), arranged front-to-back (`Y`) from smallest to largest:

1. **Slot 1 (Front)**: Small Light remote (~125 × 38 × 15 mm) $\rightarrow$ `20.0 mm` cradle slot, **`92.0 mm` tier width** (`16.5 mm` overhang per end)
2. **Slot 2 (2nd)**: Amazon Fire TV remote (~140 × 38 × 16 mm) $\rightarrow$ `20.0 mm` cradle slot, **`105.0 mm` tier width** (`17.5 mm` overhang per end)
3. **Slot 3 (3rd)**: LG TV remote (~171 × 45 × 30 mm) $\rightarrow$ `35.0 mm` cradle slot, **`128.0 mm` tier width** (`21.5 mm` overhang per end)
4. **Slot 4 (Back)**: Bose 3-2-1 series remote (~230 × 65 × 31 mm) $\rightarrow$ `36.0 mm` cradle slot, **`172.0 mm` tier width** (`29.0 mm` overhang per end)

Centered, staggered open-ended cradles (~75% of each remote's width) widen symmetrically from front to back along the $30^\circ$ tier transitions, giving every remote proportional lateral support while keeping both ends exposed for effortless pickup and minimizing couch-table footprint. A stepped, twin-rail central finger-pickup channel maintains uniform **`16.0 mm` side rails** across every staggered tier (`60.0 / 73.0 / 96.0 / 140.0 mm` wide from Tier 1 to Tier 4, widening smoothly behind each divider crest with rounded corners and a thin continuous **flat `2.4 mm` horizontal base floor**) to cut filament weight while keeping the middle of every remote open for effortless two-finger pinch pickup.

---

## 2. Parts & Assembly Architecture

| Part / Assembly | Output Files | Role & Key Features |
| :--- | :--- | :--- |
| `remote_stand` | `build/remote_stand.stl`, `build/remote_stand.step` | Single-piece printable sculptural wave stand with 4 staggered stepped $30^\circ$ cradles (`92 / 105 / 128 / 172 mm`), uniform `16.0 mm` twin support rails per tier, stepped deep central pickup channel with thin continuous flat floor (`2.4 mm`), rounded outer corners, filleted wave crests/troughs, and flat bed base (`Z = 0`). |
| `remote_boxes` | `build/remote_boxes.stl`, `build/remote_boxes.step` | Optional non-printable reference bounding boxes (`Light`, `Fire TV`, `LG`, `Bose 3-2-1`) positioned in their $30^\circ$ cradles (`--remote-boxes` / `--no-remote-boxes`). |
| `assembly` | `build/assembly.step` | Combined `Compound` (`Assembly_RemoteStand`) showing `remote_stand` together with the optional translucent remote bounding boxes seated in their cradles for fit verification. |

---

## 3. Parametric Dimensions & Configuration

All primary parameters are defined in `Config` inside `model.py`.

### Overall Form, Tilt & Ergonomics

| Parameter | `Config` Field | Default | CLI Flag | Description |
| :--- | :--- | :--- | :--- | :--- |
| Tier 1 Width (Light) | `tier1_width` | `92.0 mm` | `--tier1-width` | X span of front Light remote cradle tier |
| Tier 2 Width (Fire TV) | `tier2_width` | `105.0 mm` | `--tier2-width` | X span of 2nd Fire TV remote cradle tier |
| Tier 3 Width (LG) | `tier3_width` | `128.0 mm` | `--tier3-width` | X span of 3rd LG remote cradle tier |
| Tier 4 Width (Bose 3-2-1) | `tier4_width` | `172.0 mm` | `--tier4-width` | X span of rear Bose 3-2-1 remote cradle tier |
| Corner Radius | `corner_radius` | `10.0 mm` | — | Outer XY planform corner fillet radius per tier |
| Cradle Tilt Angle | `tilt_angle` | `30.0°` | `--tilt` | Backward lean angle of cradles from vertical |
| Base Thickness | `base_thickness` | `6.0 mm` | — | Floor Z height beneath Slot 1 back corner |
| Tier Step | `tier_step` | `4.0 mm` | `--tier-step` | Z elevation step between successive slot floors |
| Divider Rib Width | `rib_thickness` | `7.0 mm` | — | Y crest thickness of divider ribs |
| Front Lip Depth | `front_lip_depth` | `12.0 mm` | — | Front containment wall depth along tilted plane for Slot 1 |
| Wave Fillet Radius | `profile_fillet_radius` | `2.5 mm` | — | 2D fillet radius on rib crests and trough corners |
| Twin Rail Width | `rail_width` | `16.0 mm` | `--rail-width` | Uniform support rail X width per side on each staggered tier |
| Cutout Transition Fillet | `cutout_xy_fillet_radius` | `8.0 mm` | — | Horizontal 2D XY fillet radius on stepped inner pickup canyon transitions |
| Cutout Floor Z | `cutout_floor_z` | `2.4 mm` | `--cutout-floor-z` | Thin continuous flat horizontal base floor Z height inside central pickup channel |
| Cutout Floor Fillet | `cutout_fillet_radius` | `5.0 mm` | — | Concave bottom perimeter fillet radius inside central pickup channel |

### Slot Widths & Backrest Heights (Front to Back)

| Parameter | `Config` Field | Default | CLI Flag | Description |
| :--- | :--- | :--- | :--- | :--- |
| Slot 1 Width (Light) | `slot1_width` | `20.0 mm` | `--slot1-width` | Perpendicular slot width for Light remote |
| Slot 2 Width (Fire TV) | `slot2_width` | `20.0 mm` | `--slot2-width` | Perpendicular slot width for Fire TV remote |
| Slot 3 Width (LG) | `slot3_width` | `35.0 mm` | `--slot3-width` | Perpendicular slot width for LG remote |
| Slot 4 Width (Bose 3-2-1) | `slot4_width` | `36.0 mm` | `--slot4-width` | Perpendicular slot width for Bose 3-2-1 remote |
| Slot 1 Backrest | `slot1_backrest` | `28.0 mm` | — | Backrest height along $30^\circ$ plane for Slot 1 |
| Slot 2 Backrest | `slot2_backrest` | `36.0 mm` | — | Backrest height along $30^\circ$ plane for Slot 2 |
| Slot 3 Backrest | `slot3_backrest` | `42.0 mm` | — | Backrest height along $30^\circ$ plane for Slot 3 |
| Slot 4 Backrest | `slot4_backrest` | `48.0 mm` | — | Backrest height along $30^\circ$ plane for Slot 4 |

### Reference Remote Bounding Boxes (Optional Showcase)

| Parameter | `Config` Field | Default | CLI Flag | Description |
| :--- | :--- | :--- | :--- | :--- |
| Show Remote Boxes | `show_remote_boxes` | `True` | `--remote-boxes` / `--no-remote-boxes` | Toggle optional remote bounding boxes in assembly & showcase views |
| Light Remote Box | `light_length` × `light_height` × `light_thickness` | `125.0 × 38.0 × 15.0 mm` | — | Slot 1 Light remote bounding box |
| Fire TV Remote Box | `firetv_length` × `firetv_height` × `firetv_thickness` | `140.0 × 38.0 × 16.0 mm` | — | Slot 2 Fire TV remote bounding box |
| LG Remote Box | `lg_length` × `lg_height` × `lg_thickness` | `171.0 × 45.0 × 30.0 mm` | — | Slot 3 LG remote bounding box |
| Bose 3-2-1 Remote Box | `bose_length` × `bose_height` × `bose_thickness` | `230.0 × 65.0 × 31.0 mm` | — | Slot 4 Bose 3-2-1 remote bounding box |

### Derived Properties (`@property` on `Config`)
- `tier_widths`: `(tier1_width, tier2_width, tier3_width, tier4_width)` $\rightarrow$ `(92.0, 105.0, 128.0, 172.0)` mm
- `tier_cutout_widths`: `(max(20.0, tw - 2.0 * rail_width) for tw in tier_widths)` $\rightarrow$ `(60.0, 73.0, 96.0, 140.0)` mm
- `slot_widths`: `(slot1_width, slot2_width, slot3_width, slot4_width)`
- `slot_backrests`: `(slot1_backrest, slot2_backrest, slot3_backrest, slot4_backrest)`
- `slot_floor_z`: `(base_thickness + i * tier_step for i in range(4))` $\rightarrow$ `(6.0, 10.0, 14.0, 18.0)` mm

---

## 4. Functional & FDM Printability Constraints

1. **Print-Bed Adhesion**: `remote_stand` prints upright on its flat underside at `Z_min == 0.0 mm` (`bed_flat == true`), exported as its own standalone STL (`build/remote_stand.stl`).
2. **Support-Free FDM Overhangs**:
   - All cradle backrests lean at `tilt_angle = 30.0°` from vertical ($\le 45^\circ$ FDM support-free threshold).
   - Slot floors incline at $30^\circ$ above horizontal; the front outer nose leans at $30^\circ$ from vertical; the rear heel widens toward the print bed (zero overhang).
   - The stepped twin-rail pickup channel keeps `16.0 mm` vertical-walled rails above a thin continuous flat horizontal floor (`cutout_floor_z = 2.4 mm`, parallel to the print bed) with smoothed XY step transitions (`8.0 mm`) and bottom cove fillets (`5.0 mm`), dramatically reducing bulk rear solid volume while printing completely support-free.
3. **Planar Top Face**: The rear crest is bisected with `Plane.XY.offset(...)` so the highest layer finishes cleanly (`top_planar == true`, `top_normal == [0.0, 0.0, 1.0]`).
4. **Autodesk Fusion STEP Exchange**: Clean analytical and extruded/filleted B-Rep geometry exported as STEP (`AP214`).
5. **Recommended Slicer Pairing**: Print with **Lightning** infill (5–10%), **2 wall loops** (Arachne), and **3 top / 3 bottom layers** (~`0.6 mm`) alongside the stepped twin-rail + `2.4 mm` flat-floor geometry to minimize shell + infill consumption.

---

## 5. Verification & Acceptance Criteria

- **Automated Metrics (`build/metrics.json`)**:
  - `remote_stand`: `size_x == 172.0 mm` (widest Bose tier), `min_z == 0.0`, `bed_flat == true`, `top_planar == true`, solid volume reduced from `459.04 cm³` to `282.61 cm³` (`surface_area = 856.13 cm²`) while preserving all slot/tier ergonomics and flat bottom base.
  - Staggered tier widths `(92.0, 105.0, 128.0, 172.0)`, uniform `rail_width = 16.0 mm` (`60 / 73 / 96 / 140 mm` stepped cutout), `cutout_floor_z = 2.4 mm`, slot widths `(20.0, 20.0, 35.0, 36.0)`, and tilt `30.0°` verified in terminal report and `config`.
- **Visual Inspection (`preview/*_quad.png`)**:
  - `remote_stand_quad.png`: Clean symmetric stepped stagger widening front-to-back in Top & Front views with uniform `16.0 mm` left/right support rails per tier, smooth $30^\circ$ swept outer shoulders in Isometric & Side views, and a deep stepped central pickup canyon down to the thin continuous flat base floor.
  - `assembly_quad.png`: All 4 reference remotes (`125 / 140 / 171 / 230 mm` wide) bridge cleanly over the central pickup canyon on the twin `16.0 mm` side cradles with generous two-finger access around their mid-bodies and exposed ends.
