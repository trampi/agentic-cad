#!/usr/bin/env python3
"""
Parametric CAD Project Template (build123d)
Engineered for Autodesk Fusion STEP exchange and support-free FDM 3D printing.

Optimized for fast Agentic Coding:
  - Multi-view screenshots (Iso, Top, Front, Side, 2x2 Quad-View collage)
  - Geometric sanity checks & tolerance metrics in terminal and build/metrics.json
  - Fast iteration mode (--fast / --no-step)
  - Parameterized via Config dataclass and CLI flags
"""

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Dict, List

from build123d import *


# ====================================================================
# CONFIGURATION & DEFAULT PARAMETERS
# ====================================================================

@dataclass
class Config:
    # Starter part dimensions (mm) — replace/extend per SPEC.md
    width: float = field(
        default=60.0,
        metadata={"label": "Plate Width", "min": 20.0, "max": 200.0, "step": 1.0, "unit": "mm", "group": "Plate", "cli": "--width"},
    )
    length: float = field(
        default=40.0,
        metadata={"label": "Plate Length", "min": 20.0, "max": 200.0, "step": 1.0, "unit": "mm", "group": "Plate", "cli": "--length"},
    )
    thickness: float = field(
        default=6.0,
        metadata={"label": "Plate Thickness", "min": 2.0, "max": 30.0, "step": 0.5, "unit": "mm", "group": "Plate", "cli": "--thickness"},
    )
    corner_radius: float = field(
        default=4.0,
        metadata={"label": "Corner Radius", "min": 0.0, "max": 30.0, "step": 0.5, "unit": "mm", "group": "Plate"},
    )
    hole_diameter: float = field(
        default=4.5,
        metadata={"label": "Hole Diameter", "min": 0.0, "max": 16.0, "step": 0.1, "unit": "mm", "group": "Mounting Holes"},
    )
    hole_margin: float = field(
        default=8.0,
        metadata={"label": "Hole Edge Margin", "min": 3.0, "max": 30.0, "step": 0.5, "unit": "mm", "group": "Mounting Holes"},
    )

    @property
    def hole_x_offset(self) -> float:
        """X offset for symmetric mounting holes relative to center."""
        return max(0.0, self.width / 2.0 - self.hole_margin)


# ====================================================================
# PART BUILDERS (2D BEFORE 3D)
# ====================================================================

def create_base_plate(cfg: Config) -> Part:
    """Create the parametric starter base plate with symmetric mounting holes."""
    r_eff = min(cfg.corner_radius, min(cfg.width, cfg.length) / 2.0 - 0.1)
    with BuildPart() as part_bp:
        with BuildSketch(Plane.XY):
            if r_eff > 0.0:
                RectangleRounded(cfg.width, cfg.length, r_eff)
            else:
                Rectangle(cfg.width, cfg.length)
        extrude(amount=cfg.thickness)

        if cfg.hole_diameter > 0.0 and cfg.hole_x_offset > 0.0:
            with Locations((cfg.hole_x_offset, 0.0), (-cfg.hole_x_offset, 0.0)):
                Hole(radius=cfg.hole_diameter / 2.0)

    part = part_bp.part
    part.label = "BasePlate"
    return part


def build_web_parts(cfg: Config) -> List[Dict[str, Any]]:
    """Return structured part definitions for static & interactive web previews."""
    return [
        {
            "name": "base_plate",
            "shape": create_base_plate(cfg),
            "color": (0.25, 0.45, 0.75),
            "opacity": 1.0,
            "printable": True,
            "assembly_offset": (0.0, 0.0, 0.0),
            "exploded_offset": (0.0, 0.0, 0.0),
        }
    ]


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

    # Custom project-specific fit & FDM printability checks
    print("[FIT & FDM PRINTABILITY]")
    print(f"  • Plate Footprint : {cfg.width:.2f} x {cfg.length:.2f} x {cfg.thickness:.2f} mm")
    print(f"  • Mounting Holes  : Ø{cfg.hole_diameter:.2f} mm at X = ±{cfg.hole_x_offset:.2f} mm")
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
        from PIL import Image, ImageDraw

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
        description="Parametric CAD Generator (build123d)"
    )
    parser.add_argument(
        "--part",
        choices=["all", "base_plate"],
        default="all",
        help="Build only a specific part (default: all)",
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
    parser.add_argument("--width", type=float, default=None, help="Plate width in mm")
    parser.add_argument("--length", type=float, default=None, help="Plate length in mm")
    parser.add_argument("--thickness", type=float, default=None, help="Plate thickness in mm")

    args = parser.parse_args()

    cfg = Config()
    if args.width is not None:
        cfg.width = args.width
    if args.length is not None:
        cfg.length = args.length
    if args.thickness is not None:
        cfg.thickness = args.thickness

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

    if args.part in ("all", "base_plate"):
        print("\n[1/1] Building base_plate...")
        base_plate = create_base_plate(cfg)
        stl_path = b_dir / "base_plate.stl"
        export_stl(base_plate, str(stl_path))
        print(f"  ✓ STL : {stl_path}")

        if not args.fast:
            step_path = b_dir / "base_plate.step"
            export_step(base_plate, str(step_path))
            print(f"  ✓ STEP: {step_path}")

        metrics_list.append(analyze_part_geometry("base_plate", base_plate))

        csg_text = f'color([0.25, 0.45, 0.75]) import("{stl_path.resolve()}");'
        render_all_views_for_model("base_plate", csg_text, p_dir, mode=args.views)

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
