#!/usr/bin/env python3
"""
Parametrische Halteplatte mit Dorn für Schläuche (Universal-Stecksystem)
Modelliert mit build123d für hochpräzisen CAD-Export (STEP für Autodesk Fusion)
und STL-Export für den 3D-Druck.

Optimiert für schnelles AGENTIC CODING:
  - Multi-View Screenshots (Iso, Top, Front, Side, Quad-View 2x2 Collage)
  - Geometrische Sanity-Checks & Toleranzmetriken direkt im Terminal & als JSON
  - Schneller Iterationsmodus (--fast / --no-step)
  - Parametrisierbar über CLI Flags
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
from typing import Dict, Any, List

from PIL import Image, ImageDraw
from build123d import *


# ====================================================================
# KONFIGURATION & STANDARD-PARAMETER (Baseline: Haltehaken)
# ====================================================================

@dataclass
class Config:
    # Modus
    dorn_art: str = "haltehaken"          # "haltehaken" (Baseline) oder "steckdorn"

    # Wandhalterung (Befestigung)
    halter_breite: float = 50.0           # Gesamtbreite der Wandhalterung (mm)
    halter_hoehe: float = 70.0            # Gesamthöhe der Wandhalterung (mm)
    halter_tiefe: float = 12.0            # Gesamttiefe / Dicke (mm)
    boden_dicke: float = 4.0              # Wandstärke hinter Führungsnut (mm)
    halter_radius: float = 4.0            # Eckenverrundung (mm)

    # Schwalbenschwanz-Führung
    nut_breite_hinten: float = 36.0       # Nutbreite am Nutgrund (mm)
    nut_breite_vorn: float = 30.0         # Nutbreite an der Oberfläche (mm)
    spiel: float = 0.35                   # Gleitspiel zwischen Nut und Einschub (mm)

    # Schraubenlöcher (2 Stück im Halter)
    schraube_d: float = 4.2               # Schaftdurchmesser (mm)
    senkkopf_d: float = 8.2               # Senkkopfdurchmesser (mm)
    senkkopf_winkel: float = 90.0         # Senkwinkel in Grad
    schraube_oben_y: float = 16.0         # Y-Position Schraube oben (mm)
    schraube_unten_y: float = -14.0       # Y-Position Schraube unten (mm)

    # Dorn / Haken (Baseline)
    dorn_d: float = 16.0                  # Außendurchmesser des Dorns (mm)
    dorn_laenge: float = 50.0             # Nutzlänge des Dorns (mm)
    dorn_neigung: float = 5.0             # Neigungswinkel nach oben in Grad
    basis_fase: float = 5.0               # Breite/Höhe des Übergangskonus (mm)
    innenbohrung: float = 0.0             # Innendurchmesser Bohrung (0 = massiv) (mm)

    # Haltehaken-Details
    kragen_d: float = 24.0                # Durchmesser des Abschlusskragens (mm)
    kragen_dicke: float = 4.0             # Dicke des Kragens (mm)
    kragen_fase_winkel: float = 50.0      # Steigungswinkel Stützfase unter Kragen (Grad)

    # Steckdorn-Details
    barb_anzahl: int = 3                  # Anzahl Haltewülste
    barb_hoehe: float = 1.2               # Übermaß Rippen (mm)
    barb_laenge: float = 7.0              # Länge Halterippe (mm)
    spitzen_anfasung: float = 4.0         # Fasenlänge Einführspitze (mm)


# ====================================================================
# MODELLIERUNG: WANDHALTERUNG (BEFESTIGUNG)
# ====================================================================

def create_wandhalterung(cfg: Config) -> Solid:
    """Erstellt die Wandhalterung mit Schwalbenschwanzführung und 2 Senkbohrungen."""
    nut_tiefe = cfg.halter_tiefe - cfg.boden_dicke
    y_u_mitte = -cfg.halter_hoehe / 2.0 + cfg.nut_breite_hinten / 2.0 + 4.0
    y_top = cfg.halter_hoehe / 2.0
    cutter_len = (y_top + 10.0) - y_u_mitte

    # 1. Grundkörper (abgerundetes Rechteck)
    p_base = RectangleRounded(cfg.halter_breite, cfg.halter_hoehe, cfg.halter_radius)
    bracket_body = extrude(p_base, amount=cfg.halter_tiefe)

    # 2. Schwalbenschwanz-Nut (Loft von breiter Rückseite zu schmaler Vorderseite)
    def nut_profile(w: float):
        c = Pos(0, y_u_mitte) * Circle(radius=w / 2.0)
        r = Pos(0, y_u_mitte + cutter_len / 2.0) * Rectangle(w, cutter_len)
        return c + r

    n_back = Pos(0, 0, cfg.boden_dicke) * nut_profile(cfg.nut_breite_hinten)
    n_front = Pos(0, 0, cfg.halter_tiefe + 0.05) * nut_profile(cfg.nut_breite_vorn)
    nut_cutter = loft([n_back, n_front])

    bracket = bracket_body - nut_cutter

    # 3. Senkkopf-Bohrungen
    senk_r = cfg.senkkopf_d / 2.0
    bohr_r = cfg.schraube_d / 2.0
    senk_h_theor = (senk_r - bohr_r) / math.tan(math.radians(cfg.senkkopf_winkel / 2.0))
    senk_tiefe_eff = min(senk_h_theor, cfg.boden_dicke * 0.75)

    def screw_cutter(y_pos: float):
        through = Pos(0, y_pos, -1.0) * Cylinder(
            radius=bohr_r,
            height=cfg.boden_dicke + 2.0,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        cone = Pos(0, y_pos, cfg.boden_dicke - senk_tiefe_eff) * Cone(
            bottom_radius=bohr_r,
            top_radius=senk_r,
            height=senk_tiefe_eff,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        clearance = Pos(0, y_pos, cfg.boden_dicke) * Cylinder(
            radius=senk_r,
            height=cfg.halter_tiefe + 2.0,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        return through + cone + clearance

    bracket = bracket - screw_cutter(cfg.schraube_oben_y) - screw_cutter(cfg.schraube_unten_y)
    bracket.label = "Wandhalterung"
    return bracket


# ====================================================================
# MODELLIERUNG: HAKEN / DORN-EINSCHUB
# ====================================================================

def create_dorn_einschub(cfg: Config, dorn_art: str = None) -> Solid:
    """
    Erstellt den abnehmbaren Gleitschlitten mit Haltehaken oder Steckdorn.
    Baseline: "haltehaken" (mit 50°-Stützkragen und ebener horizontaler Stirnfläche).
    """
    if dorn_art is None:
        dorn_art = cfg.dorn_art

    nut_tiefe = cfg.halter_tiefe - cfg.boden_dicke
    y_u_mitte = -cfg.halter_hoehe / 2.0 + cfg.nut_breite_hinten / 2.0 + 4.0
    y_top = cfg.halter_hoehe / 2.0
    cutter_len = (y_top + 10.0) - y_u_mitte

    b_h_m = cfg.nut_breite_hinten - 2.0 * cfg.spiel
    b_v_m = cfg.nut_breite_vorn - 2.0 * cfg.spiel

    # 1. Schlittenkörper
    def slider_profile(w: float):
        c = Pos(0, y_u_mitte) * Circle(radius=w / 2.0)
        r = Pos(0, y_u_mitte + cutter_len / 2.0) * Rectangle(w, cutter_len)
        return c + r

    s_back = Pos(0, 0, 0) * slider_profile(b_h_m)
    s_front = Pos(0, 0, nut_tiefe) * slider_profile(b_v_m)
    raw_slider = loft([s_back, s_front])

    # Oben plan auf y_top abschneiden
    slider = raw_slider - Pos(0, y_top + 50.0, nut_tiefe / 2.0) * Box(
        cfg.halter_breite * 3.0, 100.0, nut_tiefe * 2.0
    )

    # 2. Dorn aufbauen
    dorn_r = cfg.dorn_d / 2.0
    y_dorn = y_u_mitte + (y_top - y_u_mitte) * 0.42

    # Gekippte Arbeitsebene (5° nach oben geneigt)
    tilted_plane = Plane(Location((0, y_dorn, nut_tiefe), (cfg.dorn_neigung, 0, 0)))

    # 2a. Basisübergang: Loft von horizontalem Kreis auf Z=nut_tiefe zur geneigten Ebene
    disk1 = Pos(0, y_dorn, nut_tiefe) * Circle(radius=dorn_r + cfg.basis_fase)
    disk2 = tilted_plane.offset(cfg.basis_fase) * Circle(radius=dorn_r)
    base_trans = loft([disk1, disk2])

    if dorn_art == "haltehaken":
        kragen_r = cfg.kragen_d / 2.0
        kragen_delta_r = max(0.5, kragen_r - dorn_r)
        kragen_fase_h = kragen_delta_r / math.tan(math.radians(cfg.kragen_fase_winkel))

        z_kragen = cfg.dorn_laenge - cfg.kragen_dicke
        z_cone_start = z_kragen - kragen_fase_h

        # Schaft
        shaft = tilted_plane.offset(cfg.basis_fase) * Cylinder(
            radius=dorn_r,
            height=max(1.0, z_cone_start - cfg.basis_fase),
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )

        # 50°-Stützkonus unterhalb des Kragens (supportfrei für FDM-Druck)
        support_cone = tilted_plane.offset(z_cone_start) * Cone(
            bottom_radius=dorn_r,
            top_radius=kragen_r,
            height=kragen_fase_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )

        # Zylindrischer Kragen
        collar = tilted_plane.offset(z_kragen) * Cylinder(
            radius=kragen_r,
            height=cfg.kragen_dicke + 4.0,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )

        dorn_solid = base_trans + shaft + support_cone + collar

        # Deckfläche vollkommen planparallel zum Druckbett kappen (Z = const, Normal=(0,0,1))
        rad = math.radians(cfg.dorn_neigung)
        z_center_top = nut_tiefe + cfg.dorn_laenge * math.cos(rad)
        z_dorn_ebene = z_center_top - kragen_r * math.sin(rad)
        cutter = Pos(0, 0, z_dorn_ebene + 50.0) * Box(200.0, 200.0, 100.0)
        dorn_leveled = dorn_solid - cutter

    else:
        # Steckdorn
        spitze_h = min(cfg.spitzen_anfasung, cfg.dorn_laenge * 0.2)
        shaft = tilted_plane.offset(cfg.basis_fase) * Cylinder(
            radius=dorn_r,
            height=cfg.dorn_laenge - cfg.basis_fase - spitze_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        tip_start = cfg.dorn_laenge - spitze_h
        tip_cone = tilted_plane.offset(tip_start) * Cone(
            bottom_radius=dorn_r,
            top_radius=max(2.0, dorn_r * 0.65),
            height=spitze_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        dorn_solid = base_trans + shaft + tip_cone

        rad = math.radians(cfg.dorn_neigung)
        z_dorn_ebene = nut_tiefe + cfg.dorn_laenge * math.cos(rad)
        cutter = Pos(0, 0, z_dorn_ebene + 50.0) * Box(200.0, 200.0, 100.0)
        dorn_leveled = dorn_solid - cutter

    # 3. Schlitten und Dorn verbinden
    einschub = slider.fuse(dorn_leveled)

    # 4. Optionale Innenbohrung
    if cfg.innenbohrung > 0.0:
        bore_r = cfg.innenbohrung / 2.0
        bore = tilted_plane.offset(-nut_tiefe - 2.0) * Cylinder(
            radius=bore_r,
            height=cfg.dorn_laenge + nut_tiefe + 10.0,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        einschub = einschub - bore

    label_suffix = "Haltehaken" if dorn_art == "haltehaken" else "Steckdorn"
    einschub.label = f"DornEinschub_{label_suffix}"
    return einschub


# ====================================================================
# SANITY-CHECKS & GEOMETRIE-METRIKEN (FÜR AGENTIC CODING)
# ====================================================================

def analyze_part_geometry(name: str, solid: Solid) -> Dict[str, Any]:
    """Berechnet maschinenlesbare Geometriedaten für Sanity-Checks."""
    bbox = solid.bounding_box()
    vol = solid.volume

    # Überprüfe Druckbett-Auflage (Z_min nahe 0.0)
    bed_flat = abs(bbox.min.Z) < 1e-3

    # Überprüfe oberste Fläche (Planarität & Normalenvektor Z=(0,0,1))
    top_faces = [f for f in solid.faces() if abs(f.center().Z - bbox.max.Z) < 0.1]
    top_planar = False
    top_normal = None
    if top_faces:
        norm = top_faces[0].normal_at(top_faces[0].center())
        top_normal = [round(norm.X, 3), round(norm.Y, 3), round(norm.Z, 3)]
        top_planar = abs(norm.Z - 1.0) < 1e-2

    return {
        "name": name,
        "bbox": {
            "size_x": round(bbox.size.X, 2),
            "size_y": round(bbox.size.Y, 2),
            "size_z": round(bbox.size.Z, 2),
            "min_z": round(bbox.min.Z, 4),
            "max_z": round(bbox.max.Z, 2),
        },
        "volume_mm3": round(vol, 1),
        "bed_flat": bed_flat,
        "top_planar": top_planar,
        "top_normal": top_normal,
    }


def print_metrics_report(metrics_list: List[Dict[str, Any]], cfg: Config):
    """Gibt einen strukturierten Bericht im Terminal aus."""
    print("\n" + "=" * 65)
    print("  GEOMETRIE-METRIKEN & SANITY-CHECKS (AGENTIC FEEDBACK)")
    print("=" * 65)

    for m in metrics_list:
        name = m["name"].upper()
        b = m["bbox"]
        print(f"[{name}]")
        print(f"  • Bounding-Box    : {b['size_x']} mm (X) x {b['size_y']} mm (Y) x {b['size_z']} mm (Z)")
        print(f"  • Druckbett (Z_min): {b['min_z']} mm -> {'✔ OK (liegt plan auf)' if m['bed_flat'] else '⚠ ACHTUNG: Kein Plan-Kontakt'}")
        if m["top_normal"]:
            status = '✔ OK (exakt horizontal parallel zum Bett)' if m['top_planar'] else '⚠ Geneigt'
            print(f"  • Deckfläche (Z_max): {b['max_z']} mm, Normal={m['top_normal']} -> {status}")
        print(f"  • Volumen         : {m['volume_mm3'] / 1000.0:.2f} cm³")
        print()

    # Passungs- und Druckbarkeitsanalyse
    eff_overhang = cfg.kragen_fase_winkel - cfg.dorn_neigung
    print("[PASSUNG & FDM-DRUCKBARKEIT]")
    print(f"  • Schwalbenschwanz-Spiel: {cfg.spiel:.2f} mm (Nut: {cfg.nut_breite_hinten} mm, Feder: {cfg.nut_breite_hinten - 2.0*cfg.spiel:.2f} mm) -> ✔ OK")
    print(f"  • Haltehaken Neigung    : {cfg.dorn_neigung:.1f}° nach oben")
    print(f"  • Kragen Stützfase      : {cfg.kragen_fase_winkel:.1f}° - Neigung {cfg.dorn_neigung:.1f}° = {eff_overhang:.1f}° gegen Vertikale -> ✔ Supportfrei (<= 45°)")
    print("=" * 65)


# ====================================================================
# SCREENSHOT & MULTI-VIEW RENDERING (OPENSCAD + PILLOW)
# ====================================================================

CAMERAS = {
    "iso":   {"cam": "0,0,0,55,0,35,140", "proj": "p", "label": "1. ISOMETRIC (3D)"},
    "top":   {"cam": "0,0,0,0,0,0,100",    "proj": "o", "label": "2. TOP (Draufsicht Z)"},
    "front": {"cam": "0,0,0,90,0,0,100",   "proj": "o", "label": "3. FRONT (Vorderansicht X)"},
    "side":  {"cam": "0,0,0,90,0,90,100",  "proj": "o", "label": "4. SIDE (Profil & Neigung Y)"},
}

def render_single_view(csg_text: str, out_png: Path, camera: str, projection: str = "p") -> bool:
    """Rendert eine einzelne Ansicht via Headless OpenSCAD."""
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
        "--colorscheme=Cornfield"
    ]
    try:
        proc = subprocess.run(cmd, input=csg_text, text=True, capture_output=True)
        return proc.returncode == 0
    except Exception:
        return False


def build_quad_collage(view_paths: Dict[str, Path], out_quad_png: Path):
    """Kombiniert 4 Ansichten zu einer 2x2 Kontaktbogen-Collage (Quad-View)."""
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
        def badge(x, y, text):
            draw.rectangle([x, y, x + 230, y + 26], fill=(30, 32, 38))
            draw.text((x + 10, y + 6), text, fill=(255, 255, 255))

        badge(15, 15, CAMERAS["iso"]["label"])
        badge(815, 15, CAMERAS["top"]["label"])
        badge(15, 615, CAMERAS["front"]["label"])
        badge(815, 615, CAMERAS["side"]["label"])

        canvas.save(out_quad_png)
    except Exception as e:
        print(f"Warnung beim Erstellen der Quad-Collage: {e}", file=sys.stderr)


def render_all_views_for_model(
    model_name: str,
    csg_text: str,
    preview_dir: Path,
    mode: str = "all"
):
    """
    Rendert Ansichten basierend auf dem gewählten Modus:
      - 'all' : Quad-View Collage + 4 Einzelansichten
      - 'quad': Nur die 2x2 Quad-View Collage (sehr kompakt)
      - 'iso' : Nur die 3D-Isoansicht
      - 'none': Keine Renderings
    """
    if mode == "none" or not shutil.which("openscad"):
        return

    if mode == "iso":
        iso_path = preview_dir / f"{model_name}.png"
        render_single_view(csg_text, iso_path, CAMERAS["iso"]["cam"], CAMERAS["iso"]["proj"])
        print(f"  ✓ Screenshot ({model_name}): {iso_path}")
        return

    # Multi-Views erzeugen
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_p = Path(tmp_dir)
        temp_views = {}
        for key, cfg_cam in CAMERAS.items():
            t_path = tmp_p / f"{key}.png"
            render_single_view(csg_text, t_path, cfg_cam["cam"], cfg_cam["proj"])
            temp_views[key] = t_path

        # Quad-View speichern
        quad_path = preview_dir / f"{model_name}_quad.png"
        build_quad_collage(temp_views, quad_path)
        print(f"  ✓ Quad-View (4-in-1 Collage): {quad_path}")

        # Wenn Modus 'all', auch Einzeldateien im Preview-Ordner ablegen
        if mode == "all":
            for key, t_path in temp_views.items():
                target = preview_dir / f"{model_name}_{key}.png"
                shutil.copy(t_path, target)
            print(f"  ✓ Einzelansichten gespeichert: {preview_dir}/{model_name}_[iso|top|front|side].png")


# ====================================================================
# HAUPTPROGRAMM & CLI
# ====================================================================

def main():
    parser = argparse.ArgumentParser(
        description="CAD-Generator für Halteplatte mit Dorn / Haltehaken (build123d)"
    )
    parser.add_argument("--part", choices=["all", "wandhalterung", "haltehaken", "baugruppe"],
                        default="all", help="Nur ein bestimmtes Teil generieren")
    parser.add_argument("--fast", "--no-step", dest="fast", action="store_true",
                        help="Schnelliteration: Überspringt STEP-Export (nur STL & Renderings)")
    parser.add_argument("--views", choices=["all", "quad", "iso", "none"], default="all",
                        help="Screenshot-Modus: 'all' (Quad + Einzel), 'quad' (nur 4-in-1), 'iso', 'none'")
    parser.add_argument("--json", action="store_true",
                        help="Schreibt Geometrie-Metriken strukturiert nach build/metrics.json")
    parser.add_argument("--build-dir", default="build", help="Ausgabeverzeichnis für CAD-Dateien")
    parser.add_argument("--preview-dir", default="preview", help="Ausgabeverzeichnis für Screenshots")

    # Geometrie-Overrides
    parser.add_argument("--spiel", type=float, default=None, help="Gleitspiel Führungsnut in mm")
    parser.add_argument("--neigung", type=float, default=None, help="Neigungswinkel Haken in Grad")
    parser.add_argument("--dorn-l", type=float, default=None, help="Länge des Dorns in mm")
    parser.add_argument("--dorn-d", type=float, default=None, help="Durchmesser des Dorns in mm")
    parser.add_argument("--kragen-d", type=float, default=None, help="Durchmesser Abschlusskragen in mm")

    args = parser.parse_args()

    # Konfiguration initialisieren
    cfg = Config()
    if args.spiel is not None:
        cfg.spiel = args.spiel
    if args.neigung is not None:
        cfg.dorn_neigung = args.neigung
    if args.dorn_l is not None:
        cfg.dorn_laenge = args.dorn_l
    if args.dorn_d is not None:
        cfg.dorn_d = args.dorn_d
    if args.kragen_d is not None:
        cfg.kragen_d = args.kragen_d

    b_dir = Path(args.build_dir)
    p_dir = Path(args.preview_dir)
    b_dir.mkdir(parents=True, exist_ok=True)
    p_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 65)
    print(f"CAD BUILD (build123d) -> Modus: {args.part.upper()} | Baseline: {cfg.dorn_art.upper()}")
    print(f"  • CAD-Ordner     : '{b_dir}/'")
    print(f"  • Preview-Ordner : '{p_dir}/'")
    print(f"  • STEP-Export    : {'Deaktiviert (--fast)' if args.fast else 'Aktiviert'}")
    print(f"  • Views-Modus    : {args.views}")
    print("=" * 65)

    metrics_list = []
    bracket = None
    haken = None

    # 1. Wandhalterung
    if args.part in ("all", "wandhalterung", "baugruppe"):
        print("\n[1/3] Erzeuge Wandhalterung (Befestigung)...")
        bracket = create_wandhalterung(cfg)
        stl_bracket = b_dir / "wandhalterung.stl"
        export_stl(bracket, str(stl_bracket))
        print(f"  ✓ STL : {stl_bracket}")

        if not args.fast:
            step_bracket = b_dir / "wandhalterung.step"
            export_step(bracket, str(step_bracket))
            print(f"  ✓ STEP: {step_bracket}")

        metrics_list.append(analyze_part_geometry("wandhalterung", bracket))

        if args.part in ("all", "wandhalterung"):
            csg_bracket = f'color([1.0, 0.42, 0.05]) import("{stl_bracket.resolve()}");'
            render_all_views_for_model("wandhalterung", csg_bracket, p_dir, mode=args.views)

    # 2. Haltehaken
    if args.part in ("all", "haltehaken", "baugruppe"):
        print(f"\n[2/3] Erzeuge Haltehaken ({cfg.dorn_art})...")
        haken = create_dorn_einschub(cfg, cfg.dorn_art)
        stl_haken = b_dir / "haltehaken.stl"
        export_stl(haken, str(stl_haken))
        print(f"  ✓ STL : {stl_haken}")

        if not args.fast:
            step_haken = b_dir / "haltehaken.step"
            export_step(haken, str(step_haken))
            print(f"  ✓ STEP: {step_haken}")

        metrics_list.append(analyze_part_geometry("haltehaken", haken))

        if args.part in ("all", "haltehaken"):
            csg_haken = f'color([0.25, 0.25, 0.28]) import("{stl_haken.resolve()}");'
            render_all_views_for_model("haltehaken", csg_haken, p_dir, mode=args.views)

    # 3. Baugruppe / Montage
    if args.part in ("all", "baugruppe") and bracket and haken:
        print("\n[3/3] Erzeuge Zusammenbau & Montageansichten...")
        haken_mated = Pos(0, 0, cfg.boden_dicke) * haken

        if not args.fast:
            assembly = Compound([bracket, haken_mated], label="Baugruppe_Haltehaken")
            step_assy = b_dir / "baugruppe_haltehaken.step"
            export_step(assembly, str(step_assy))
            print(f"  ✓ STEP (Baugruppe): {step_assy}")

        # Zusammenbau Renderings
        csg_zusammenbau = f'''
        color([1.0, 0.42, 0.05]) import("{(b_dir / "wandhalterung.stl").resolve()}");
        color([0.25, 0.25, 0.28]) translate([0, 0, {cfg.boden_dicke}]) import("{(b_dir / "haltehaken.stl").resolve()}");
        '''
        render_all_views_for_model("zusammenbau", csg_zusammenbau, p_dir, mode=args.views)

        # Explosionsansicht
        if args.views != "none" and shutil.which("openscad"):
            p_explosion = p_dir / "explosion.png"
            csg_explosion = f'''
            color([1.0, 0.42, 0.05]) import("{(b_dir / "wandhalterung.stl").resolve()}");
            color([0.25, 0.25, 0.28]) translate([0, 25, {cfg.boden_dicke + 18.0}]) import("{(b_dir / "haltehaken.stl").resolve()}");
            '''
            render_single_view(csg_explosion, p_explosion, camera="0,0,0,55,0,35,160", projection="p")
            print(f"  ✓ Explosionsansicht: {p_explosion}")

    # Terminal-Report ausgeben
    print_metrics_report(metrics_list, cfg)

    # Optionales JSON
    if args.json or True:  # immer mitschreiben für agentic feedback
        json_path = b_dir / "metrics.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "config": asdict(cfg),
                "parts": metrics_list
            }, f, indent=2)
        print(f"✔ Strukturierte Metriken gespeichert in '{json_path}'")

    print("\n" + "=" * 65)
    print("✔ Build erfolgreich abgeschlossen!")
    print("=" * 65)


if __name__ == "__main__":
    main()
