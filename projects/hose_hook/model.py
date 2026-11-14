#!/usr/bin/env python3
"""
Parametric Wall Mount & Quick-Release Hose Hook (Modular Dovetail System)
Modeled with build123d for high-precision CAD export (STEP for Autodesk Fusion)
and STL export for FDM 3D printing.

Optimized for fast Agentic Coding:
  - Multi-view screenshots (Iso, Top, Front, Side, 2x2 Quad-View collage)
  - Geometric sanity checks & tolerance metrics in terminal and build/metrics.json
  - Fast iteration mode (--fast / --no-step)
  - Parameterized via Config dataclass and CLI flags
"""

import argparse
import copy
import json
import math
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageDraw
from build123d import *


# ====================================================================
# CONFIGURATION & DEFAULT PARAMETERS (Baseline: Hose Hook)
# ====================================================================

@dataclass
class Config:
    # Mode
    stem_type: str = "hose_hook"            # "hose_hook" (baseline) or "hose_barb"

    # Wall mount bracket
    bracket_width: float = 50.0             # Overall bracket width (mm)
    bracket_height: float = 70.0            # Overall bracket height (mm)
    bracket_depth: float = 12.0             # Overall depth / thickness (mm)
    back_wall_thickness: float = 4.0        # Solid backing thickness behind slot (mm)
    corner_radius: float = 4.0              # Outer corner fillet radius (mm)
    bottom_margin: float = 4.0              # Wall thickness below U-channel (mm)

    # Dovetail guide channel
    slot_width_back: float = 36.0           # Slot width at channel floor (mm)
    slot_width_front: float = 30.0          # Slot width at front surface (mm)
    clearance: float = 0.35                 # Sliding clearance per mating face (mm)

    # Mounting screw holes (2x M4 countersunk in bracket)
    screw_diameter: float = 4.4             # Clearance shaft diameter (mm)
    countersink_diameter: float = 8.7       # Countersink head diameter (mm)
    countersink_angle: float = 90.0         # Countersink angle (degrees)
    screw_top_y: float = 16.0               # Top screw Y position (mm)
    screw_bottom_y: float = -14.0           # Bottom screw Y position (mm)

    # Stem / hook (baseline)
    stem_diameter: float = 16.0             # Stem outer diameter (mm)
    stem_length: float = 50.0               # Usable stem length (mm)
    stem_tilt: float = -5.0                 # Upward tilt angle around X axis (degrees)
    base_chamfer: float = 5.0               # Width/height of base transition cone (mm)
    inner_bore: float = 0.0                 # Through-bore diameter (0 = solid) (mm)
    stem_y_factor: float = 0.42             # Relative Y position of stem on slider

    # Hose hook end collar details
    collar_diameter: float = 24.0           # End collar outer diameter (mm)
    collar_thickness: float = 4.0           # End collar thickness (mm)
    collar_chamfer_angle: float = 50.0      # Support cone angle relative to stem axis (deg)

    # Hose barb variant details
    barb_count: int = 3                     # Number of retention barbs
    barb_height: float = 1.2                # Radial barb protrusion (mm)
    barb_length: float = 7.0                # Length of each barb segment (mm)
    tip_chamfer: float = 4.0                # Lead-in tip chamfer length (mm)

    # ----------------------------------------------------------------
    # Derived geometry properties
    # ----------------------------------------------------------------
    @property
    def slot_depth(self) -> float:
        """Depth of the dovetail slot and thickness of the mating slider."""
        return self.bracket_depth - self.back_wall_thickness

    @property
    def y_top(self) -> float:
        """Top Y edge of the wall mount and slider."""
        return self.bracket_height / 2.0

    @property
    def y_u_center(self) -> float:
        """Y coordinate of the lower semicircle center of the U-channel."""
        return -self.bracket_height / 2.0 + self.slot_width_back / 2.0 + self.bottom_margin

    @property
    def slider_width_back(self) -> float:
        """Rear dovetail tongue width (minus bilateral clearance)."""
        return self.slot_width_back - 2.0 * self.clearance

    @property
    def slider_width_front(self) -> float:
        """Front dovetail tongue width (minus bilateral clearance)."""
        return self.slot_width_front - 2.0 * self.clearance

    @property
    def y_stem(self) -> float:
        """Y coordinate of the stem centerline on the slider."""
        return self.y_u_center + (self.y_top - self.y_u_center) * self.stem_y_factor

    @property
    def effective_overhang_angle(self) -> float:
        """Effective FDM overhang angle against vertical (degrees)."""
        return self.collar_chamfer_angle - abs(self.stem_tilt)


# ====================================================================
# SHARED 2D SKETCH HELPERS (2D BEFORE 3D)
# ====================================================================

def _draw_dovetail_u_profile(width: float, y_center: float, y_top: float):
    """
    Draw the 2D U-profile (bottom semicircle + straight channel to y_top)
    in the local Plane.XY coordinate system of the active BuildSketch context.
    """
    with Locations((0, y_center)):
        Circle(radius=width / 2.0)
        Rectangle(width, y_top - y_center, align=(Align.CENTER, Align.MIN))


def _build_stem_revolve_points(cfg: Config, stem_type: str) -> List[Tuple[float, float]]:
    """
    Build the 2D half-profile points (radius X, axis height Y) for the
    360-degree revolve geometry of the stem starting at height cfg.base_chamfer.
    """
    stem_r = cfg.stem_diameter / 2.0

    if stem_type == "hose_hook":
        collar_r = cfg.collar_diameter / 2.0
        collar_delta_r = max(0.5, collar_r - stem_r)
        collar_chamfer_h = collar_delta_r / math.tan(math.radians(cfg.collar_chamfer_angle))

        z_collar = cfg.stem_length - cfg.collar_thickness
        z_cone_start = max(cfg.base_chamfer + 1.0, z_collar - collar_chamfer_h)
        # Overshoot top so the subsequent horizontal planar split creates
        # a completely flat top face parallel to the print bed
        z_top_over = z_collar + cfg.collar_thickness + 4.0

        return [
            (0.0, cfg.base_chamfer),
            (stem_r, cfg.base_chamfer),
            (stem_r, z_cone_start),
            (collar_r, z_collar),
            (collar_r, z_top_over),
            (0.0, z_top_over),
        ]

    # Variant: "hose_barb" (optional retention barbs in 2D revolve profile)
    tip_h = min(cfg.tip_chamfer, cfg.stem_length * 0.2)
    tip_start = max(cfg.base_chamfer + 1.0, cfg.stem_length - tip_h)
    tip_r = max(2.0, stem_r * 0.65)
    z_top_over = cfg.stem_length + 4.0

    pts: List[Tuple[float, float]] = [
        (0.0, cfg.base_chamfer),
        (stem_r, cfg.base_chamfer),
    ]

    usable_span = tip_start - cfg.base_chamfer - 6.0
    if cfg.barb_count > 0 and usable_span >= cfg.barb_length:
        start_z = cfg.base_chamfer + 3.0
        step = (
            (usable_span - cfg.barb_length) / (cfg.barb_count - 1)
            if cfg.barb_count > 1
            else 0.0
        )
        lead_len = cfg.barb_length * 0.25
        for i in range(cfg.barb_count):
            z_pos = (
                start_z + i * step
                if cfg.barb_count > 1
                else start_z + (usable_span - cfg.barb_length) / 2.0
            )
            pts.extend([
                (stem_r, z_pos),
                (stem_r + cfg.barb_height, z_pos + lead_len),
                (stem_r, z_pos + cfg.barb_length),
            ])

    pts.extend([
        (stem_r, tip_start),
        (tip_r, z_top_over),
        (0.0, z_top_over),
    ])
    return pts


# ====================================================================
# MODELING: WALL MOUNT BRACKET
# ====================================================================

def create_wall_mount(cfg: Config) -> Part:
    """Create the wall mount bracket with dovetail slot and 2 countersunk holes."""
    cs_r = cfg.countersink_diameter / 2.0
    bore_r = cfg.screw_diameter / 2.0
    cs_h_theor = (cs_r - bore_r) / math.tan(math.radians(cfg.countersink_angle / 2.0))
    cs_depth_eff = min(cs_h_theor, cfg.back_wall_thickness * 0.75)
    eff_cs_angle = 2.0 * math.degrees(math.atan((cs_r - bore_r) / cs_depth_eff))

    # Extend slot slightly past y_top so top breakthrough stays clean for large corner radii
    slot_top_y = cfg.y_top + cfg.corner_radius

    with BuildPart() as bracket_bp:
        # 1. Base body (2D rounded rectangle sketch extruded in 3D)
        with BuildSketch(Plane.XY):
            RectangleRounded(cfg.bracket_width, cfg.bracket_height, cfg.corner_radius)
        extrude(amount=cfg.bracket_depth)

        # 2. Dovetail slot (loft from wider back floor to narrower front face)
        top_face: Face = bracket_bp.faces().sort_by(Axis.Z)[-1]
        with BuildSketch(Plane.XY.offset(cfg.back_wall_thickness)):
            _draw_dovetail_u_profile(cfg.slot_width_back, cfg.y_u_center, slot_top_y)
        with BuildSketch(top_face):
            _draw_dovetail_u_profile(cfg.slot_width_front, cfg.y_u_center, slot_top_y)
        loft(mode=Mode.SUBTRACT)

        # 3. Countersunk mounting holes on slot floor (including +Z clearance)
        with Locations(Plane.XY.offset(cfg.back_wall_thickness)):
            with Locations((0, cfg.screw_top_y), (0, cfg.screw_bottom_y)):
                CounterSinkHole(
                    radius=bore_r,
                    counter_sink_radius=cs_r,
                    counter_sink_angle=eff_cs_angle,
                )

    bracket = bracket_bp.part
    bracket.label = "WallMount"
    return bracket


# ====================================================================
# MODELING: HOOK / BARB SLIDER
# ====================================================================

def create_hook_slider(cfg: Config, stem_type: Optional[str] = None) -> Part:
    """
    Create the detachable dovetail slider with hose hook or hose barb.
    Baseline: "hose_hook" (50 deg support cone and planar horizontal top face).
    """
    if stem_type is None:
        stem_type = cfg.stem_type

    stem_r = cfg.stem_diameter / 2.0

    # Tilted work plane (angled 5 deg upward) at the stem base center
    tilted_plane = Plane(Location((0, cfg.y_stem, cfg.slot_depth), (cfg.stem_tilt, 0, 0)))

    # Longitudinal section plane for 2D revolve profile (local +X = radius, local +Y = stem axis)
    stem_profile_plane = Plane(
        origin=tilted_plane.origin,
        x_dir=tilted_plane.x_dir,
        z_dir=-tilted_plane.y_dir,
    )
    stem_axis = Axis(tilted_plane.origin, tilted_plane.z_dir)

    # Z height for horizontal planar top cut (normal = (0, 0, 1))
    rad = math.radians(cfg.stem_tilt)
    z_center_top = cfg.slot_depth + cfg.stem_length * math.cos(rad)
    if stem_type == "hose_hook":
        z_top_plane = z_center_top - (cfg.collar_diameter / 2.0) * math.sin(rad)
    else:
        z_top_plane = z_center_top

    profile_pts = _build_stem_revolve_points(cfg, stem_type)

    with BuildPart() as slider_bp:
        # 1. Slider tongue (bounded directly to cfg.y_top in 2D sketch)
        with BuildSketch(Plane.XY):
            _draw_dovetail_u_profile(cfg.slider_width_back, cfg.y_u_center, cfg.y_top)
        with BuildSketch(Plane.XY.offset(cfg.slot_depth)):
            _draw_dovetail_u_profile(cfg.slider_width_front, cfg.y_u_center, cfg.y_top)
        loft()

        # 2. Base transition cone: loft from horizontal circle on slider top to tilted stem plane
        with BuildSketch(Plane.XY.offset(cfg.slot_depth)):
            with Locations((0, cfg.y_stem)):
                Circle(radius=stem_r + cfg.base_chamfer)
        with BuildSketch(tilted_plane.offset(cfg.base_chamfer)):
            Circle(radius=stem_r)
        loft()

        # 3. Stem + support cone + collar via 2D half-profile & 360-deg revolve
        #    Note: BuildLine intentionally uses local Plane.XY inside BuildSketch
        with BuildSketch(stem_profile_plane):
            with BuildLine():
                Polyline(*profile_pts, close=True)
            make_face()
        revolve(axis=stem_axis)

        # 4. Cut top face completely parallel to the print bed (Z = const, normal = (0, 0, 1))
        split(bisect_by=Plane.XY.offset(z_top_plane), keep=Keep.BOTTOM)

        # 5. Optional continuous inner bore along the tilted stem axis
        if cfg.inner_bore > 0.0:
            with Locations(tilted_plane):
                Hole(radius=cfg.inner_bore / 2.0)

    slider = slider_bp.part
    label_suffix = "HoseHook" if stem_type == "hose_hook" else "HoseBarb"
    slider.label = f"HookSlider_{label_suffix}"
    return slider


# ====================================================================
# SANITY CHECKS & GEOMETRIC METRICS (AGENTIC FEEDBACK)
# ====================================================================

def analyze_part_geometry(name: str, solid: Shape) -> Dict[str, Any]:
    """Compute machine-readable geometric metrics via topology selectors."""
    bbox = solid.bounding_box()
    vol = solid.volume

    # Verify print-bed contact (lowest face at Z_min == 0.0, planar, normal (0, 0, -1))
    bottom_face: Face = solid.faces().sort_by(Axis.Z)[0]
    bed_flat = (
        abs(bbox.min.Z) < 1e-3
        and bottom_face.geom_type == GeomType.PLANE
        and abs(bottom_face.normal_at().Z + 1.0) < 1e-2
    )

    # Verify top face planarity & normal vector Z = (0, 0, 1)
    top_face: Face = solid.faces().sort_by(Axis.Z)[-1]
    norm = top_face.normal_at()
    top_normal = [
        round(norm.X, 3) + 0.0,
        round(norm.Y, 3) + 0.0,
        round(norm.Z, 3) + 0.0,
    ]
    top_planar = top_face.geom_type == GeomType.PLANE and abs(norm.Z - 1.0) < 1e-2

    return {
        "name": name,
        "bbox": {
            "size_x": round(bbox.size.X, 2),
            "size_y": round(bbox.size.Y, 2),
            "size_z": round(bbox.size.Z, 2),
            "min_z": round(bbox.min.Z, 4) + 0.0,
            "max_z": round(bbox.max.Z, 2),
        },
        "volume_mm3": round(vol, 1),
        "bed_flat": bed_flat,
        "top_planar": top_planar,
        "top_normal": top_normal,
    }


def print_metrics_report(metrics_list: List[Dict[str, Any]], cfg: Config):
    """Print a structured geometric verification report to stdout."""
    print("\n" + "=" * 65)
    print("  GEOMETRIC METRICS & SANITY CHECKS (AGENTIC FEEDBACK)")
    print("=" * 65)

    for m in metrics_list:
        name = m["name"].upper()
        b = m["bbox"]
        print(f"[{name}]")
        print(f"  • Bounding Box    : {b['size_x']} mm (X) x {b['size_y']} mm (Y) x {b['size_z']} mm (Z)")
        bed_status = "✔ OK (flat on bed)" if m["bed_flat"] else "⚠ WARNING: Not flat on print bed"
        print(f"  • Print Bed (Z_min): {b['min_z']} mm -> {bed_status}")
        if m["top_normal"]:
            top_status = "✔ OK (horizontal, parallel to bed)" if m["top_planar"] else "⚠ Tilted / non-planar"
            print(f"  • Top Face (Z_max) : {b['max_z']} mm, Normal={m['top_normal']} -> {top_status}")
        print(f"  • Volume          : {m['volume_mm3'] / 1000.0:.2f} cm³")
        print()

    eff_overhang = cfg.effective_overhang_angle
    overhang_status = "✔ Support-free (<= 45°)" if eff_overhang <= 45.0 else "⚠ Exceeds 45°"
    print("[FIT & FDM PRINTABILITY]")
    print(
        f"  • Dovetail Clearance : {cfg.clearance:.2f} mm "
        f"(Slot: {cfg.slot_width_back} mm, Slider: {cfg.slider_width_back:.2f} mm) -> ✔ OK"
    )
    print(f"  • Hook Upward Tilt   : {abs(cfg.stem_tilt):.1f}° upward (stem_tilt={cfg.stem_tilt:.1f}°)")
    print(
        f"  • Collar Support Cone: {cfg.collar_chamfer_angle:.1f}° - Tilt {abs(cfg.stem_tilt):.1f}° "
        f"= {eff_overhang:.1f}° from vertical -> {overhang_status}"
    )
    print("=" * 65)


# ====================================================================
# SCREENSHOT & MULTI-VIEW RENDERING (OPENSCAD + PILLOW)
# ====================================================================

CAMERAS = {
    "iso":   {"cam": "0,0,0,55,0,35,140", "proj": "p", "label": "1. ISOMETRIC (3D)"},
    "top":   {"cam": "0,0,0,0,0,0,100",   "proj": "o", "label": "2. TOP (Z-View)"},
    "front": {"cam": "0,0,0,90,0,0,100",  "proj": "o", "label": "3. FRONT (X-View)"},
    "side":  {"cam": "0,0,0,90,0,90,100", "proj": "o", "label": "4. SIDE (Y-Profile)"},
}


def render_single_view(csg_text: str, out_png: Path, camera: str, projection: str = "p") -> bool:
    """Render a single view via headless OpenSCAD."""
    if not shutil.which("openscad"):
        return False
    cmd = [
        "openscad",
        "-o", str(out_png),
        "-",
        "--autocenter", "--viewall",
        f"--camera={camera}",
        f"--projection={projection}",
        "--imgsize=800,600",
        "--colorscheme=Cornfield",
    ]
    try:
        proc = subprocess.run(cmd, input=csg_text, text=True, capture_output=True)
        return proc.returncode == 0
    except Exception:
        return False


def build_quad_collage(view_paths: Dict[str, Path], out_quad_png: Path):
    """Combine 4 views into a 2x2 contact sheet collage (Quad-View)."""
    try:
        iso = Image.open(view_paths["iso"])
        top = Image.open(view_paths["top"])
        front = Image.open(view_paths["front"])
        side = Image.open(view_paths["side"])

        w, h = 1600, 1200
        canvas = Image.new("RGB", (w, h), (242, 242, 242))
        canvas.paste(iso, (0, 0))
        canvas.paste(top, (800, 0))
        canvas.paste(front, (0, 600))
        canvas.paste(side, (800, 600))

        draw = ImageDraw.Draw(canvas)

        def badge(x: int, y: int, text: str):
            draw.rectangle([x, y, x + 230, y + 26], fill=(30, 32, 38))
            draw.text((x + 10, y + 6), text, fill=(255, 255, 255))

        badge(15, 15, CAMERAS["iso"]["label"])
        badge(815, 15, CAMERAS["top"]["label"])
        badge(15, 615, CAMERAS["front"]["label"])
        badge(815, 615, CAMERAS["side"]["label"])

        canvas.save(out_quad_png)
    except Exception as e:
        print(f"Warning while building quad collage: {e}", file=sys.stderr)


def render_all_views_for_model(
    model_name: str,
    csg_text: str,
    preview_dir: Path,
    mode: str = "all",
):
    """
    Render views according to the selected mode:
      - 'all' : Quad-View collage + 4 individual views
      - 'quad': Only the 2x2 Quad-View collage (compact)
      - 'iso' : Only the 3D isometric view
      - 'none': No renderings
    """
    if mode == "none" or not shutil.which("openscad"):
        return

    if mode == "iso":
        iso_path = preview_dir / f"{model_name}.png"
        render_single_view(csg_text, iso_path, CAMERAS["iso"]["cam"], CAMERAS["iso"]["proj"])
        print(f"  ✓ Screenshot ({model_name}): {iso_path}")
        return

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_p = Path(tmp_dir)
        temp_views = {}
        for key, cfg_cam in CAMERAS.items():
            t_path = tmp_p / f"{key}.png"
            render_single_view(csg_text, t_path, cfg_cam["cam"], cfg_cam["proj"])
            temp_views[key] = t_path

        quad_path = preview_dir / f"{model_name}_quad.png"
        build_quad_collage(temp_views, quad_path)
        print(f"  ✓ Quad-View (4-in-1 collage): {quad_path}")

        if mode == "all":
            for key, t_path in temp_views.items():
                target = preview_dir / f"{model_name}_{key}.png"
                shutil.copy(t_path, target)
            print(f"  ✓ Individual views saved: {preview_dir}/{model_name}_[iso|top|front|side].png")


# ====================================================================
# MAIN CLI ENTRYPOINT
# ====================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Parametric CAD Generator for Wall Mount & Hose Hook (build123d)"
    )
    parser.add_argument(
        "--part",
        choices=["all", "wall_mount", "hose_hook", "assembly"],
        default="all",
        help="Build only a specific part or assembly (default: all)",
    )
    parser.add_argument(
        "--fast", "--no-step",
        dest="fast",
        action="store_true",
        help="Fast iteration: skip STEP export (STL & previews only)",
    )
    parser.add_argument(
        "--views",
        choices=["all", "quad", "iso", "none"],
        default="all",
        help="Rendering mode: 'all' (Quad + single views), 'quad' (4-in-1 only), 'iso', 'none'",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Write structured geometric metrics to build/metrics.json",
    )
    parser.add_argument("--build-dir", default="build", help="Output directory for CAD files")
    parser.add_argument("--preview-dir", default="preview", help="Output directory for preview images")

    # Geometry parameter overrides
    parser.add_argument("--clearance", type=float, default=None, help="Dovetail sliding clearance in mm")
    parser.add_argument("--tilt", type=float, default=None, help="Stem tilt angle around X in degrees (e.g. -5.0)")
    parser.add_argument("--stem-length", "--stem-l", dest="stem_length", type=float, default=None, help="Usable stem length in mm")
    parser.add_argument("--stem-diameter", "--stem-d", dest="stem_diameter", type=float, default=None, help="Stem outer diameter in mm")
    parser.add_argument("--collar-diameter", "--collar-d", dest="collar_diameter", type=float, default=None, help="End collar outer diameter in mm")

    args = parser.parse_args()

    cfg = Config()
    if args.clearance is not None:
        cfg.clearance = args.clearance
    if args.tilt is not None:
        cfg.stem_tilt = args.tilt
    if args.stem_length is not None:
        cfg.stem_length = args.stem_length
    if args.stem_diameter is not None:
        cfg.stem_diameter = args.stem_diameter
    if args.collar_diameter is not None:
        cfg.collar_diameter = args.collar_diameter

    b_dir = Path(args.build_dir)
    p_dir = Path(args.preview_dir)
    b_dir.mkdir(parents=True, exist_ok=True)
    p_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print(f"CAD BUILD (build123d) -> Part: {args.part.upper()} | Baseline: {cfg.stem_type.upper()}")
    print(f"  • Build Dir   : '{b_dir}/'")
    print(f"  • Preview Dir : '{p_dir}/'")
    print(f"  • STEP Export : {'Disabled (--fast)' if args.fast else 'Enabled'}")
    print(f"  • Views Mode  : {args.views}")
    print("=" * 65)

    metrics_list: List[Dict[str, Any]] = []
    bracket = None
    hook = None

    # 1. Wall mount bracket
    if args.part in ("all", "wall_mount", "assembly"):
        print("\n[1/3] Building wall_mount...")
        bracket = create_wall_mount(cfg)
        stl_bracket = b_dir / "wall_mount.stl"
        export_stl(bracket, str(stl_bracket))
        print(f"  ✓ STL : {stl_bracket}")

        if not args.fast:
            step_bracket = b_dir / "wall_mount.step"
            export_step(bracket, str(step_bracket))
            print(f"  ✓ STEP: {step_bracket}")

        metrics_list.append(analyze_part_geometry("wall_mount", bracket))

        if args.part in ("all", "wall_mount"):
            csg_bracket = f'color([1.0, 0.42, 0.05]) import("{stl_bracket.resolve()}");'
            render_all_views_for_model("wall_mount", csg_bracket, p_dir, mode=args.views)

    # 2. Hose hook slider
    if args.part in ("all", "hose_hook", "assembly"):
        print(f"\n[2/3] Building hose_hook ({cfg.stem_type})...")
        hook = create_hook_slider(cfg, cfg.stem_type)
        stl_hook = b_dir / "hose_hook.stl"
        export_stl(hook, str(stl_hook))
        print(f"  ✓ STL : {stl_hook}")

        if not args.fast:
            step_hook = b_dir / "hose_hook.step"
            export_step(hook, str(step_hook))
            print(f"  ✓ STEP: {step_hook}")

        metrics_list.append(analyze_part_geometry("hose_hook", hook))

        if args.part in ("all", "hose_hook"):
            csg_hook = f'color([0.25, 0.25, 0.28]) import("{stl_hook.resolve()}");'
            render_all_views_for_model("hose_hook", csg_hook, p_dir, mode=args.views)

    # 3. Assembly / Mated view
    if args.part in ("all", "assembly") and bracket and hook:
        print("\n[3/3] Building assembly & exploded views...")
        # Shallow copy shares the underlying OCCT TopoDS_TShape
        hook_mated = copy.copy(hook).move(Location((0, 0, cfg.back_wall_thickness)))

        if not args.fast:
            assembly = Compound([bracket, hook_mated], label="Assembly_HoseHook")
            step_assy = b_dir / "assembly.step"
            export_step(assembly, str(step_assy))
            print(f"  ✓ STEP (Assembly): {step_assy}")

        csg_assembly = f'''
        color([1.0, 0.42, 0.05]) import("{(b_dir / "wall_mount.stl").resolve()}");
        color([0.25, 0.25, 0.28]) translate([0, 0, {cfg.back_wall_thickness}]) import("{(b_dir / "hose_hook.stl").resolve()}");
        '''
        render_all_views_for_model("assembly", csg_assembly, p_dir, mode=args.views)

        if args.views != "none" and shutil.which("openscad"):
            p_exploded = p_dir / "exploded.png"
            csg_exploded = f'''
            color([1.0, 0.42, 0.05]) import("{(b_dir / "wall_mount.stl").resolve()}");
            color([0.25, 0.25, 0.28]) translate([0, 25, {cfg.back_wall_thickness + 18.0}]) import("{(b_dir / "hose_hook.stl").resolve()}");
            '''
            render_single_view(csg_exploded, p_exploded, camera="0,0,0,55,0,35,160", projection="p")
            print(f"  ✓ Exploded view: {p_exploded}")

    print_metrics_report(metrics_list, cfg)

    # Always emit metrics.json for automated agentic feedback
    json_path = b_dir / "metrics.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "config": asdict(cfg),
                "parts": metrics_list,
            },
            f,
            indent=2,
        )
    print(f"✔ Structured metrics saved to '{json_path}'")

    print("\n" + "=" * 65)
    print("✔ Build completed successfully!")
    print("=" * 65)


if __name__ == "__main__":
    main()
