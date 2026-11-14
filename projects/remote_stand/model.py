#!/usr/bin/env python3
"""
Parametric 4-Slot Couch-Table Remote Stand (Sculptural Stepped Wave Cradle)
Modeled with build123d for high-precision CAD export (STEP for Autodesk Fusion)
and STL export for support-free FDM 3D printing.

Optimized for fast Agentic Coding:
  - Multi-view screenshots (Iso, Top, Front, Side, 2x2 Quad-View collage)
  - Geometric sanity checks & tolerance metrics in terminal and build/metrics.json
  - Fast iteration mode (--fast / --no-step)
  - Parameterized via Config dataclass and CLI flags
"""

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

from PIL import Image, ImageDraw
from build123d import *


# ====================================================================
# CONFIGURATION & DEFAULT PARAMETERS
# ====================================================================

@dataclass
class Config:
    # Staggered cradle X-widths (front to back: ~75% of each remote's length)
    tier1_width: float = 92.0               # Slot 1 (Light, 125 mm) cradle X width (mm)
    tier2_width: float = 105.0              # Slot 2 (Fire TV, 140 mm) cradle X width (mm)
    tier3_width: float = 128.0              # Slot 3 (LG, 171 mm) cradle X width (mm)
    tier4_width: float = 172.0              # Slot 4 (Bose 3-2-1, 230 mm) cradle X width (mm)

    # Overall stand footprint & aesthetic styling
    corner_radius: float = 10.0             # Outer XY planform corner fillet radius per tier (mm)
    tilt_angle: float = 30.0                # Cradle backward tilt from vertical (degrees)
    base_thickness: float = 6.0             # Z thickness beneath Slot 1 back corner (mm)
    tier_step: float = 4.0                  # Z elevation step between successive slot floors (mm)
    rib_thickness: float = 7.0              # Y crest width of divider ribs (mm)
    front_lip_depth: float = 12.0           # Front containment height along tilted plane (mm)
    profile_fillet_radius: float = 2.5      # 2D fillet radius for crests and troughs (mm)
    rail_width: float = 16.0                # Uniform side support rail width per tier (mm)
    cutout_xy_fillet_radius: float = 8.0    # 2D XY fillet radius on stepped canyon transitions (mm)
    cutout_floor_z: float = 2.4             # Thin continuous flat horizontal floor Z in canyon (mm)
    cutout_fillet_radius: float = 5.0       # Bottom perimeter cove fillet radius in canyon (mm)

    # Perpendicular slot widths (front to back: Light, Fire TV, LG, Bose 3-2-1)
    slot1_width: float = 20.0               # Slot 1 (Front): Small Light remote (mm)
    slot2_width: float = 20.0               # Slot 2: Amazon Fire TV remote (mm)
    slot3_width: float = 35.0               # Slot 3: LG TV remote (mm)
    slot4_width: float = 36.0               # Slot 4 (Back): Bose 3-2-1 remote (mm)

    # Backrest heights along the 30-degree tilted plane (mm)
    slot1_backrest: float = 28.0            # Slot 1 backrest length (mm)
    slot2_backrest: float = 36.0            # Slot 2 backrest length (mm)
    slot3_backrest: float = 42.0            # Slot 3 backrest length (mm)
    slot4_backrest: float = 48.0            # Slot 4 backrest length (mm)

    # Reference remote bounding boxes (optional showcase & fit verification)
    show_remote_boxes: bool = True          # Toggle reference bounding boxes in assembly
    light_length: float = 125.0             # Slot 1 Light remote length X (mm)
    light_height: float = 38.0              # Slot 1 Light remote height (mm)
    light_thickness: float = 15.0           # Slot 1 Light remote thickness (mm)
    firetv_length: float = 140.0            # Slot 2 Fire TV remote length X (mm)
    firetv_height: float = 38.0             # Slot 2 Fire TV remote height (mm)
    firetv_thickness: float = 16.0          # Slot 2 Fire TV remote thickness (mm)
    lg_length: float = 171.0                # Slot 3 LG remote length X (mm)
    lg_height: float = 45.0                 # Slot 3 LG remote height (mm)
    lg_thickness: float = 30.0              # Slot 3 LG remote thickness (mm)
    bose_length: float = 230.0              # Slot 4 Bose 3-2-1 remote length X (mm)
    bose_height: float = 65.0               # Slot 4 Bose 3-2-1 remote height (mm)
    bose_thickness: float = 31.0            # Slot 4 Bose 3-2-1 remote thickness (mm)

    # ----------------------------------------------------------------
    # Derived geometry properties
    # ----------------------------------------------------------------
    @property
    def tier_widths(self) -> Tuple[float, float, float, float]:
        return (self.tier1_width, self.tier2_width, self.tier3_width, self.tier4_width)

    @property
    def tier_cutout_widths(self) -> Tuple[float, float, float, float]:
        return tuple(max(20.0, tw - 2.0 * self.rail_width) for tw in self.tier_widths)  # type: ignore

    @property
    def slot_widths(self) -> Tuple[float, float, float, float]:
        return (self.slot1_width, self.slot2_width, self.slot3_width, self.slot4_width)

    @property
    def slot_backrests(self) -> Tuple[float, float, float, float]:
        return (
            self.slot1_backrest,
            self.slot2_backrest,
            self.slot3_backrest,
            self.slot4_backrest,
        )

    @property
    def slot_floor_z(self) -> Tuple[float, float, float, float]:
        return tuple(self.base_thickness + i * self.tier_step for i in range(4))  # type: ignore


# ====================================================================
# 2D SIDE-PROFILE & CRADLE GEOMETRY (2D BEFORE 3D)
# ====================================================================

def _compute_cradle_geometry(cfg: Config) -> Dict[str, Any]:
    """
    Compute exact 2D side-profile polygon points in (Y, Z) along with
    slot corner coordinates and divider crest intervals.
    """
    rad = math.radians(cfg.tilt_angle)
    sin_t = math.sin(rad)
    cos_t = math.cos(rad)
    tan_t = math.tan(rad)

    # Unit vectors in (Y, Z):
    # u: up & back along backrest; t: back & down along slot floor
    u_y, u_z = sin_t, cos_t
    t_y, t_z = cos_t, -sin_t

    widths = cfg.slot_widths
    backrests = cfg.slot_backrests
    floor_zs = cfg.slot_floor_z

    profile_pts: List[Tuple[float, float]] = [(0.0, 0.0)]
    crest_spans: List[Tuple[float, float, float]] = []  # (y_start, y_end, z_crest)
    slot_origins: List[Tuple[float, float]] = []        # (y_back_floor, z_back_floor)
    backrest_tops: List[Tuple[float, float]] = []       # (y_back_top, z_back_top)

    prev_bt: Tuple[float, float] = (0.0, 0.0)

    for i in range(4):
        w_i = widths[i]
        z_b = floor_zs[i]
        z_ff = z_b + w_i * sin_t

        if i == 0:
            z_ft = z_ff + cfg.front_lip_depth * cos_t
            y_nose_top = z_ft * tan_t
            front_crest_w = cfg.rib_thickness * 0.85
            y_ft = y_nose_top + front_crest_w

            p_nose_top = (y_nose_top, z_ft)
            p_ft = (y_ft, z_ft)
            p_ff = (y_ft - cfg.front_lip_depth * u_y, z_ft - cfg.front_lip_depth * u_z)
            p_b = (p_ff[0] + w_i * t_y, p_ff[1] + w_i * t_z)

            profile_pts.extend([p_nose_top, p_ft, p_ff, p_b])
            crest_spans.append((y_nose_top, y_ft, z_ft))
        else:
            y_ft = prev_bt[0] + cfg.rib_thickness
            z_ft = prev_bt[1]
            p_ft = (y_ft, z_ft)

            delta_s = (z_ft - z_ff) / cos_t
            p_ff = (y_ft - delta_s * u_y, z_ft - delta_s * u_z)
            p_b = (p_ff[0] + w_i * t_y, p_ff[1] + w_i * t_z)

            profile_pts.extend([p_ft, p_ff, p_b])
            crest_spans.append((prev_bt[0], y_ft, z_ft))

        slot_origins.append(p_b)

        # Ensure backrest clears next slot's front containment wall by at least 8 mm along u
        d_eff = backrests[i]
        if i < 3:
            next_z_ff = floor_zs[i + 1] + widths[i + 1] * sin_t
            min_z_bt = next_z_ff + 8.0 * cos_t
            d_min = (min_z_bt - p_b[1]) / cos_t
            d_eff = max(d_eff, d_min)

        p_bt = (p_b[0] + d_eff * u_y, p_b[1] + d_eff * u_z)
        profile_pts.append(p_bt)
        backrest_tops.append(p_bt)
        prev_bt = p_bt

    # Rear top crest and sloped rear heel down to Z = 0
    y_rear_top = prev_bt[0] + cfg.rib_thickness
    z_max = prev_bt[1]
    y_total = y_rear_top + 4.0

    crest_spans.append((prev_bt[0], y_rear_top, z_max))
    profile_pts.append((y_rear_top, z_max))
    profile_pts.append((y_total, 0.0))

    return {
        "profile_pts": profile_pts,
        "crest_spans": crest_spans,
        "slot_origins": slot_origins,
        "backrest_tops": backrest_tops,
        "y_total": y_total,
        "z_max": z_max,
    }


# ====================================================================
# MODELING: REMOTE STAND & REFERENCE ASSEMBLY
# ====================================================================

def _create_stepped_pickup_cutout(
    cfg: Config,
    backrest_tops: List[Tuple[float, float]],
    y_total: float,
    z_max: float,
) -> Part:
    """
    Build the stepped twin-rail central pickup channel cutter above `cutout_floor_z`.
    Widens behind each divider crest so every tier retains uniform side rails.
    """
    cut_w = cfg.tier_cutout_widths
    z_bot = cfg.cutout_floor_z
    z_top_cut = z_max + 8.0

    pts_right: List[Tuple[float, float]] = [(cut_w[0] / 2.0, -5.0)]
    for i in range(3):
        dw = cut_w[i + 1] - cut_w[i]
        if abs(dw) <= 0.5:
            continue
        y_step_start = backrest_tops[i][0] + 1.0
        dy = max(10.0, abs(dw) * 0.5)
        pts_right.append((cut_w[i] / 2.0, y_step_start))
        pts_right.append((cut_w[i + 1] / 2.0, y_step_start + dy))
    pts_right.append((cut_w[3] / 2.0, y_total + 5.0))

    pts_poly = pts_right + [(-x, y) for x, y in reversed(pts_right)]

    with BuildPart() as cut_bp:
        with BuildSketch(Plane.XY.offset(z_bot)):
            with BuildLine():
                Polyline(*pts_poly, close=True)
            make_face()
            interior_verts = [v for v in vertices() if -2.0 < v.Y < y_total + 2.0]
            if interior_verts and cfg.cutout_xy_fillet_radius > 0.0:
                fillet(interior_verts, radius=cfg.cutout_xy_fillet_radius)
        extrude(amount=z_top_cut - z_bot)

        if cfg.cutout_fillet_radius > 0.0:
            bot_edges = cut_bp.edges().filter_by(lambda e: abs(e.center().Z - z_bot) < 0.05)
            if bot_edges:
                fillet(bot_edges, radius=cfg.cutout_fillet_radius)

    return cut_bp.part


def create_remote_stand(cfg: Config) -> Part:
    """Create the single-piece sculptural 4-slot staggered couch-table remote stand."""
    geom = _compute_cradle_geometry(cfg)
    profile_pts = geom["profile_pts"]
    crest_spans = geom["crest_spans"]
    backrest_tops = geom["backrest_tops"]
    y_total = geom["y_total"]
    z_max = geom["z_max"]

    tier_widths = cfg.tier_widths
    max_w = max(tier_widths)
    tan_t = math.tan(math.radians(cfg.tilt_angle))

    # Explicit YZ plane: local +X = global +Y, local +Y = global +Z, local +Z = global +X
    yz_plane = Plane(origin=(0, 0, 0), x_dir=(0, 1, 0), z_dir=(1, 0, 0))

    # 1. Master full-width wave solid (2D fillets before 3D extrusion)
    with BuildPart() as wave_bp:
        with BuildSketch(yz_plane):
            with BuildLine():
                Polyline(*profile_pts, close=True)
            make_face()
            above_bed_verts = [v for v in vertices() if v.Y > 1.0]
            if above_bed_verts and cfg.profile_fillet_radius > 0.0:
                fillet(above_bed_verts, radius=cfg.profile_fillet_radius)
        extrude(amount=max_w / 2.0, both=True)
    master_wave = wave_bp.part

    # 2. Slice master_wave into 4 centered staggered tiers along the 30-deg transitions
    tier_parts: List[Part] = []
    overlap = 1.0
    for i, tier_w in enumerate(tier_widths):
        if i == 0:
            y_fb_bot = -2.0
            y_fb_top = -2.0
            y_rect_front = 0.0
        else:
            y_bt_prev, z_bt_prev = backrest_tops[i - 1]
            y_fb_bot = y_bt_prev - z_bt_prev * tan_t
            y_fb_top = y_bt_prev + (z_max + 2.0 - z_bt_prev) * tan_t
            y_rect_front = y_fb_bot

        if i < 3:
            y_bt_curr, z_bt_curr = backrest_tops[i]
            y_bb_bot = y_bt_curr + overlap - z_bt_curr * tan_t
            y_bb_top = y_bt_curr + overlap + (z_max + 2.0 - z_bt_curr) * tan_t
            y_rect_back = max(y_bb_bot, y_bt_curr + overlap) + cfg.corner_radius + 2.0
        else:
            y_bb_bot = y_total + 5.0
            y_bb_top = y_total + 5.0
            y_rect_back = y_total

        rect_len = y_rect_back - y_rect_front
        r_eff = min(cfg.corner_radius, tier_w / 2.0 - 1.0, rect_len / 2.0 - 1.0)

        with BuildPart() as tier_bp:
            insert(master_wave)
            # 30-degree angled tier slice in (Y, Z)
            slice_pts = [
                (y_fb_bot, -1.0),
                (y_bb_bot, -1.0),
                (y_bb_top, z_max + 2.0),
                (y_fb_top, z_max + 2.0),
            ]
            with BuildSketch(yz_plane):
                with BuildLine():
                    Polyline(*slice_pts, close=True)
                make_face()
            extrude(amount=max_w / 2.0 + 2.0, both=True, mode=Mode.INTERSECT)

            # Tier X width & rounded XY planform corners
            with BuildSketch(Plane.XY):
                with Locations((0.0, (y_rect_front + y_rect_back) / 2.0)):
                    if r_eff > 0.0:
                        RectangleRounded(tier_w, rect_len, r_eff)
                    else:
                        Rectangle(tier_w, rect_len)
            extrude(amount=z_max + 5.0, mode=Mode.INTERSECT)

        tier_parts.append(tier_bp.part)

    with BuildPart() as stand_bp:
        for t_part in tier_parts:
            insert(t_part)

        # 3. Sculpt stepped twin-rail central pickup canyon with thin continuous flat floor
        if cfg.rail_width > 0.0:
            cut_solid = _create_stepped_pickup_cutout(cfg, backrest_tops, y_total, z_max)
            insert(cut_solid, mode=Mode.SUBTRACT)

        # 4. Guarantee a clean horizontal planar top crest (Normal = (0, 0, 1))
        split(bisect_by=Plane.XY.offset(z_max - 0.35), keep=Keep.BOTTOM)

    stand = stand_bp.part
    stand.label = "RemoteStand"
    return stand


def create_remote_bounding_boxes(cfg: Config) -> List[Tuple[str, Part, Tuple[float, float, float]]]:
    """
    Create 4 crisp rectangular reference bounding boxes seated in their cradles
    to showcase remote fit, proportions, and clearances (non-printable reference).
    """
    geom = _compute_cradle_geometry(cfg)
    slot_origins = geom["slot_origins"]

    # (name, length_X, height_edge_to_edge, thickness, rgb_color)
    remote_specs = [
        ("LightRemoteBox",   cfg.light_length,  cfg.light_height,  cfg.light_thickness,  (0.92, 0.78, 0.25)),
        ("FireTVRemoteBox",  cfg.firetv_length, cfg.firetv_height, cfg.firetv_thickness, (0.90, 0.45, 0.20)),
        ("LGRemoteBox",      cfg.lg_length,     cfg.lg_height,     cfg.lg_thickness,     (0.30, 0.70, 0.55)),
        ("Bose321RemoteBox", cfg.bose_length,   cfg.bose_height,   cfg.bose_thickness,   (0.55, 0.48, 0.82)),
    ]

    parts: List[Tuple[str, Part, Tuple[float, float, float]]] = []
    for i, (r_name, r_len, r_height, r_thick, color) in enumerate(remote_specs):
        y_b, z_b = slot_origins[i]
        slot_plane = Plane(Location((0.0, y_b, z_b), (-cfg.tilt_angle, 0.0, 0.0)))

        # Center remote in X, offset slightly off backrest & floor by 1.0 mm clearance
        offset_y_local = -(r_thick / 2.0 + 1.0)
        offset_z_local = r_height / 2.0 + 1.0
        center_world = slot_plane.origin + slot_plane.y_dir * offset_y_local + slot_plane.z_dir * offset_z_local

        with BuildPart() as rem_bp:
            rem_plane = Plane(Location(center_world, (-cfg.tilt_angle, 0.0, 0.0)))
            with BuildSketch(rem_plane.offset(-r_height / 2.0)):
                Rectangle(r_len, r_thick)
            extrude(amount=r_height)

        rem = rem_bp.part
        rem.label = r_name
        parts.append((r_name, rem, color))

    return parts


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
        "surface_area_mm2": round(solid.area, 1),
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
        print(f"  • Surface Area    : {m['surface_area_mm2'] / 100.0:.2f} cm²")
        print()

    overhang_status = "✔ Support-free (<= 45°)" if cfg.tilt_angle <= 45.0 else "⚠ Exceeds 45°"
    cut_w = "/".join(f"{w:.0f}" for w in cfg.tier_cutout_widths)
    print("[FIT & FDM PRINTABILITY]")
    print(f"  • Tier Widths (F->B): Light={cfg.tier1_width} mm, FireTV={cfg.tier2_width} mm, LG={cfg.tier3_width} mm, Bose={cfg.tier4_width} mm")
    print(f"  • Slot Widths (F->B): Light={cfg.slot1_width} mm, FireTV={cfg.slot2_width} mm, LG={cfg.slot3_width} mm, Bose={cfg.slot4_width} mm")
    print(f"  • Cradle Tilt Angle : {cfg.tilt_angle:.1f}° from vertical -> {overhang_status}")
    print(f"  • Stepped Cutout    : {cut_w} mm wide (rail={cfg.rail_width:.1f} mm/side), flat floor Z={cfg.cutout_floor_z:.1f} mm")
    print(f"  • Remote BBoxes     : {'Enabled' if cfg.show_remote_boxes else 'Disabled (--no-remote-boxes)'} ({cfg.light_length}/{cfg.firetv_length}/{cfg.lg_length}/{cfg.bose_length} mm)")
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
        description="Parametric CAD Generator for 4-Slot Couch-Table Remote Stand (build123d)"
    )
    parser.add_argument(
        "--part",
        choices=["all", "remote_stand", "remote_boxes", "assembly"],
        default="all",
        help="Build only a specific part or assembly (default: all)",
    )
    parser.add_argument(
        "--remote-boxes",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Show/hide optional remote bounding boxes in assembly showcase (default: enabled)",
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
    parser.add_argument("--build-dir", default="build", help="Output directory for CAD artifacts")
    parser.add_argument("--preview-dir", default="preview", help="Output directory for preview images")

    # Geometry parameter overrides
    parser.add_argument("--tier1-width", type=float, default=None, help="Tier 1 (Light remote) cradle width in mm")
    parser.add_argument("--tier2-width", type=float, default=None, help="Tier 2 (Fire TV remote) cradle width in mm")
    parser.add_argument("--tier3-width", type=float, default=None, help="Tier 3 (LG remote) cradle width in mm")
    parser.add_argument("--tier4-width", type=float, default=None, help="Tier 4 (Bose 3-2-1 remote) cradle width in mm")
    parser.add_argument("--tilt", type=float, default=None, help="Cradle tilt angle from vertical in degrees")
    parser.add_argument("--tier-step", type=float, default=None, help="Z elevation step between slots in mm")
    parser.add_argument("--rail-width", type=float, default=None, help="Uniform left/right support rail width per tier in mm")
    parser.add_argument("--cutout-floor-z", type=float, default=None, help="Thin flat base floor Z height inside center cutout in mm")
    parser.add_argument("--slot1-width", type=float, default=None, help="Slot 1 (Light remote) width in mm")
    parser.add_argument("--slot2-width", type=float, default=None, help="Slot 2 (Fire TV remote) width in mm")
    parser.add_argument("--slot3-width", type=float, default=None, help="Slot 3 (LG remote) width in mm")
    parser.add_argument("--slot4-width", type=float, default=None, help="Slot 4 (Bose 3-2-1 remote) width in mm")

    args = parser.parse_args()

    cfg = Config()
    if args.remote_boxes is not None:
        cfg.show_remote_boxes = args.remote_boxes
    if args.tier1_width is not None:
        cfg.tier1_width = args.tier1_width
    if args.tier2_width is not None:
        cfg.tier2_width = args.tier2_width
    if args.tier3_width is not None:
        cfg.tier3_width = args.tier3_width
    if args.tier4_width is not None:
        cfg.tier4_width = args.tier4_width
    if args.tilt is not None:
        cfg.tilt_angle = args.tilt
    if args.tier_step is not None:
        cfg.tier_step = args.tier_step
    if args.rail_width is not None:
        cfg.rail_width = args.rail_width
    if args.cutout_floor_z is not None:
        cfg.cutout_floor_z = args.cutout_floor_z
    if args.slot1_width is not None:
        cfg.slot1_width = args.slot1_width
    if args.slot2_width is not None:
        cfg.slot2_width = args.slot2_width
    if args.slot3_width is not None:
        cfg.slot3_width = args.slot3_width
    if args.slot4_width is not None:
        cfg.slot4_width = args.slot4_width

    b_dir = Path(args.build_dir)
    p_dir = Path(args.preview_dir)
    b_dir.mkdir(parents=True, exist_ok=True)
    p_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print(f"CAD BUILD (build123d) -> Part: {args.part.upper()}")
    print(f"  • Build Dir   : '{b_dir}/'")
    print(f"  • Preview Dir : '{p_dir}/'")
    print(f"  • STEP Export : {'Disabled (--fast)' if args.fast else 'Enabled'}")
    print(f"  • Views Mode  : {args.views}")
    print("=" * 65)

    metrics_list: List[Dict[str, Any]] = []
    stand = None
    stl_stand = b_dir / "remote_stand.stl"

    # 1. Printable Remote Stand
    if args.part in ("all", "remote_stand", "assembly"):
        print("\n[1/3] Building remote_stand...")
        stand = create_remote_stand(cfg)
        export_stl(stand, str(stl_stand))
        print(f"  ✓ STL : {stl_stand}")

        if not args.fast:
            step_stand = b_dir / "remote_stand.step"
            export_step(stand, str(step_stand))
            print(f"  ✓ STEP: {step_stand}")

        metrics_list.append(analyze_part_geometry("remote_stand", stand))

        if args.part in ("all", "remote_stand"):
            csg_stand = f'color([0.22, 0.36, 0.46]) import("{stl_stand.resolve()}");'
            render_all_views_for_model("remote_stand", csg_stand, p_dir, mode=args.views)

    # 2. Optional Remote Bounding Boxes (standalone or assembly showcase)
    ref_boxes = None
    if args.part == "remote_boxes" or (args.part in ("all", "assembly") and cfg.show_remote_boxes):
        print("\n[2/3] Building optional remote bounding boxes...")
        ref_boxes = create_remote_bounding_boxes(cfg)

        if args.part == "remote_boxes":
            boxes_compound = Compound([r_part for _, r_part, _ in ref_boxes], label="RemoteBoundingBoxes")
            stl_boxes = b_dir / "remote_boxes.stl"
            export_stl(boxes_compound, str(stl_boxes))
            print(f"  ✓ STL : {stl_boxes}")

            if not args.fast:
                step_boxes = b_dir / "remote_boxes.step"
                export_step(boxes_compound, str(step_boxes))
                print(f"  ✓ STEP: {step_boxes}")

            if args.views != "none" and shutil.which("openscad"):
                with tempfile.TemporaryDirectory() as tmp_box_dir:
                    tmp_box_p = Path(tmp_box_dir)
                    csg_lines = []
                    for r_name, r_part, rgb in ref_boxes:
                        r_stl = tmp_box_p / f"{r_name}.stl"
                        export_stl(r_part, str(r_stl))
                        csg_lines.append(
                            f'color([{rgb[0]}, {rgb[1]}, {rgb[2]}, 0.55]) import("{r_stl.resolve()}");'
                        )
                    render_all_views_for_model("remote_boxes", "\n".join(csg_lines), p_dir, mode=args.views)

    # 3. Showcase Assembly (stand + optional translucent remote bounding boxes)
    if args.part in ("all", "assembly") and stand is not None:
        box_label = "with 4 translucent remote bounding boxes" if cfg.show_remote_boxes else "stand only (--no-remote-boxes)"
        print(f"\n[3/3] Building assembly ({box_label})...")

        if not args.fast:
            assy_parts = [stand] + ([r_part for _, r_part, _ in ref_boxes] if ref_boxes else [])
            assembly = Compound(assy_parts, label="Assembly_RemoteStand")
            step_assy = b_dir / "assembly.step"
            export_step(assembly, str(step_assy))
            print(f"  ✓ STEP (Assembly): {step_assy}")

        if args.views != "none" and shutil.which("openscad"):
            with tempfile.TemporaryDirectory() as tmp_ref_dir:
                tmp_ref_p = Path(tmp_ref_dir)
                csg_lines = [f'color([0.22, 0.36, 0.46]) import("{stl_stand.resolve()}");']
                if ref_boxes:
                    for r_name, r_part, rgb in ref_boxes:
                        r_stl = tmp_ref_p / f"{r_name}.stl"
                        export_stl(r_part, str(r_stl))
                        csg_lines.append(
                            f'color([{rgb[0]}, {rgb[1]}, {rgb[2]}, 0.35]) import("{r_stl.resolve()}");'
                        )
                render_all_views_for_model("assembly", "\n".join(csg_lines), p_dir, mode=args.views)

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
