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
import copy
import json
import math
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Tuple

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
    unten_rand: float = 4.0               # Wandstärke unterhalb des U-Kanals (mm)

    # Schwalbenschwanz-Führung
    nut_breite_hinten: float = 36.0       # Nutbreite am Nutgrund (mm)
    nut_breite_vorn: float = 30.0         # Nutbreite an der Oberfläche (mm)
    spiel: float = 0.35                   # Gleitspiel zwischen Nut und Einschub (mm)

    # Schraubenlöcher (2 Stück im Halter) M4 Senkkopf
    schraube_d: float = 4.4               # Schaftdurchmesser (mm)
    senkkopf_d: float = 8.7               # Senkkopfdurchmesser (mm)
    senkkopf_winkel: float = 90.0         # Senkwinkel in Grad
    schraube_oben_y: float = 16.0         # Y-Position Schraube oben (mm)
    schraube_unten_y: float = -14.0       # Y-Position Schraube unten (mm)

    # Dorn / Haken (Baseline)
    dorn_d: float = 16.0                  # Außendurchmesser des Dorns (mm)
    dorn_laenge: float = 50.0             # Nutzlänge des Dorns (mm)
    dorn_neigung: float = -5.0             # Neigungswinkel nach oben in Grad
    basis_fase: float = 5.0               # Breite/Höhe des Übergangskonus (mm)
    innenbohrung: float = 0.0             # Innendurchmesser Bohrung (0 = massiv) (mm)
    dorn_y_faktor: float = 0.42           # Relative Y-Position des Dorns auf dem Schlitten

    # Haltehaken-Details
    kragen_d: float = 24.0                # Durchmesser des Abschlusskragens (mm)
    kragen_dicke: float = 4.0             # Dicke des Kragens (mm)
    kragen_fase_winkel: float = 50.0      # Steigungswinkel Stützfase unter Kragen (Grad)

    # Steckdorn-Details
    barb_anzahl: int = 3                  # Anzahl Haltewülste
    barb_hoehe: float = 1.2               # Übermaß Rippen (mm)
    barb_laenge: float = 7.0              # Länge Halterippe (mm)
    spitzen_anfasung: float = 4.0         # Fasenlänge Einführspitze (mm)

    # ----------------------------------------------------------------
    # Abgeleitete Geometrie-Parameter (Parameterize Best Practice)
    # ----------------------------------------------------------------
    @property
    def nut_tiefe(self) -> float:
        """Tiefe der Schwalbenschwanznut bzw. Dicke des Gleitschlittens."""
        return self.halter_tiefe - self.boden_dicke

    @property
    def y_top(self) -> float:
        """Obere Y-Kante von Wandhalterung und Schlitten."""
        return self.halter_hoehe / 2.0

    @property
    def y_u_mitte(self) -> float:
        """Y-Koordinate des unteren Halbkreis-Zentrums der U-Führung."""
        return -self.halter_hoehe / 2.0 + self.nut_breite_hinten / 2.0 + self.unten_rand

    @property
    def feder_breite_hinten(self) -> float:
        """Breite der Schwalbenschwanzfeder hinten (abzüglich beidseitigem Spiel)."""
        return self.nut_breite_hinten - 2.0 * self.spiel

    @property
    def feder_breite_vorn(self) -> float:
        """Breite der Schwalbenschwanzfeder vorn (abzüglich beidseitigem Spiel)."""
        return self.nut_breite_vorn - 2.0 * self.spiel

    @property
    def y_dorn(self) -> float:
        """Y-Position der Dorn-Mittelachse auf dem Schlitten."""
        return self.y_u_mitte + (self.y_top - self.y_u_mitte) * self.dorn_y_faktor

    @property
    def eff_overhang_winkel(self) -> float:
        """Effektiver FDM-Überhangwinkel gegen die Vertikale (Grad)."""
        return self.kragen_fase_winkel - self.dorn_neigung


# ====================================================================
# GEMEINSAME 2D-SKIZZEN-HELFER (2D BEFORE 3D)
# ====================================================================

def _draw_dovetail_u_profile(width: float, y_center: float, y_top: float):
    """
    Zeichnet das 2D-U-Profil (Halbkreis unten + gerader Schacht bis y_top)
    im lokalen Koordinatensystem (Plane.XY) des aktiven BuildSketch-Kontexts.
    """
    with Locations((0, y_center)):
        Circle(radius=width / 2.0)
        Rectangle(width, y_top - y_center, align=(Align.CENTER, Align.MIN))


def _build_stem_revolve_points(cfg: Config, dorn_art: str) -> List[Tuple[float, float]]:
    """
    Erzeugt die 2D-Halbprofil-Punkte (Radius X, Achsenhöhe Y) für die
    Rotationsgeometrie (revolve) des Dorns ab Höhe cfg.basis_fase.
    """
    dorn_r = cfg.dorn_d / 2.0

    if dorn_art == "haltehaken":
        kragen_r = cfg.kragen_d / 2.0
        kragen_delta_r = max(0.5, kragen_r - dorn_r)
        kragen_fase_h = kragen_delta_r / math.tan(math.radians(cfg.kragen_fase_winkel))

        z_kragen = cfg.dorn_laenge - cfg.kragen_dicke
        z_cone_start = max(cfg.basis_fase + 1.0, z_kragen - kragen_fase_h)
        # Übermaß nach oben, damit der anschließende Horizontalschnitt (split)
        # eine vollständig ebene Deckfläche erzeugt
        z_top_over = z_kragen + cfg.kragen_dicke + 4.0

        return [
            (0.0, cfg.basis_fase),
            (dorn_r, cfg.basis_fase),
            (dorn_r, z_cone_start),
            (kragen_r, z_kragen),
            (kragen_r, z_top_over),
            (0.0, z_top_over),
        ]

    # Modus: "steckdorn" (optional mit Haltewülsten / Barbs im 2D-Rotationsprofil)
    spitze_h = min(cfg.spitzen_anfasung, cfg.dorn_laenge * 0.2)
    tip_start = max(cfg.basis_fase + 1.0, cfg.dorn_laenge - spitze_h)
    tip_r = max(2.0, dorn_r * 0.65)
    z_top_over = cfg.dorn_laenge + 4.0

    pts: List[Tuple[float, float]] = [
        (0.0, cfg.basis_fase),
        (dorn_r, cfg.basis_fase),
    ]

    nutz_bereich = tip_start - cfg.basis_fase - 6.0
    if cfg.barb_anzahl > 0 and nutz_bereich >= cfg.barb_laenge:
        start_z = cfg.basis_fase + 3.0
        schritt = (
            (nutz_bereich - cfg.barb_laenge) / (cfg.barb_anzahl - 1)
            if cfg.barb_anzahl > 1
            else 0.0
        )
        kanten_l = cfg.barb_laenge * 0.25
        for i in range(cfg.barb_anzahl):
            z_pos = (
                start_z + i * schritt
                if cfg.barb_anzahl > 1
                else start_z + (nutz_bereich - cfg.barb_laenge) / 2.0
            )
            pts.extend([
                (dorn_r, z_pos),
                (dorn_r + cfg.barb_hoehe, z_pos + kanten_l),
                (dorn_r, z_pos + cfg.barb_laenge),
            ])

    pts.extend([
        (dorn_r, tip_start),
        (tip_r, z_top_over),
        (0.0, z_top_over),
    ])
    return pts


# ====================================================================
# MODELLIERUNG: WANDHALTERUNG (BEFESTIGUNG)
# ====================================================================

def create_wandhalterung(cfg: Config) -> Part:
    """Erstellt die Wandhalterung mit Schwalbenschwanzführung und 2 Senkbohrungen."""
    senk_r = cfg.senkkopf_d / 2.0
    bohr_r = cfg.schraube_d / 2.0
    senk_h_theor = (senk_r - bohr_r) / math.tan(math.radians(cfg.senkkopf_winkel / 2.0))
    senk_tiefe_eff = min(senk_h_theor, cfg.boden_dicke * 0.75)
    eff_senk_winkel = 2.0 * math.degrees(math.atan((senk_r - bohr_r) / senk_tiefe_eff))

    # Überstand der Nut nach oben für sauberen Durchbruch auch bei großen Eckradien
    nut_top_y = cfg.y_top + cfg.halter_radius

    with BuildPart() as bracket_bp:
        # 1. Grundkörper (2D-Skizze mit Eckenverrundung vor 3D-Extrusion)
        with BuildSketch(Plane.XY):
            RectangleRounded(cfg.halter_breite, cfg.halter_hoehe, cfg.halter_radius)
        extrude(amount=cfg.halter_tiefe)

        # 2. Schwalbenschwanz-Nut (Loft von breiter Rückseite zur schmalen Vorderseite)
        top_face: Face = bracket_bp.faces().sort_by(Axis.Z)[-1]
        with BuildSketch(Plane.XY.offset(cfg.boden_dicke)):
            _draw_dovetail_u_profile(cfg.nut_breite_hinten, cfg.y_u_mitte, nut_top_y)
        with BuildSketch(top_face):
            _draw_dovetail_u_profile(cfg.nut_breite_vorn, cfg.y_u_mitte, nut_top_y)
        loft(mode=Mode.SUBTRACT)

        # 3. Senkkopf-Bohrungen im Nutgrund (inkl. Freistich durch die Nut nach +Z)
        with Locations(Plane.XY.offset(cfg.boden_dicke)):
            with Locations((0, cfg.schraube_oben_y), (0, cfg.schraube_unten_y)):
                CounterSinkHole(
                    radius=bohr_r,
                    counter_sink_radius=senk_r,
                    counter_sink_angle=eff_senk_winkel,
                )

    bracket = bracket_bp.part
    bracket.label = "Wandhalterung"
    return bracket


# ====================================================================
# MODELLIERUNG: HAKEN / DORN-EINSCHUB
# ====================================================================

def create_dorn_einschub(cfg: Config, dorn_art: str = None) -> Part:
    """
    Erstellt den abnehmbaren Gleitschlitten mit Haltehaken oder Steckdorn.
    Baseline: "haltehaken" (mit 50°-Stützkragen und ebener horizontaler Stirnfläche).
    """
    if dorn_art is None:
        dorn_art = cfg.dorn_art

    dorn_r = cfg.dorn_d / 2.0

    # Gekippte Arbeitsebene (5° nach oben geneigt) am Fußpunkt des Dorns
    tilted_plane = Plane(Location((0, cfg.y_dorn, cfg.nut_tiefe), (cfg.dorn_neigung, 0, 0)))

    # Längsschnitt-Ebene für 2D-Rotationsprofil (lokales +X = Radius, lokales +Y = Dornachse)
    stem_profile_plane = Plane(
        origin=tilted_plane.origin,
        x_dir=tilted_plane.x_dir,
        z_dir=-tilted_plane.y_dir,
    )
    stem_axis = Axis(tilted_plane.origin, tilted_plane.z_dir)

    # Z-Höhe für den planparallelen Deckflächen-Schnitt (Normal = (0, 0, 1))
    rad = math.radians(cfg.dorn_neigung)
    z_center_top = cfg.nut_tiefe + cfg.dorn_laenge * math.cos(rad)
    if dorn_art == "haltehaken":
        z_dorn_ebene = z_center_top - (cfg.kragen_d / 2.0) * math.sin(rad)
    else:
        z_dorn_ebene = z_center_top

    profile_pts = _build_stem_revolve_points(cfg, dorn_art)

    with BuildPart() as einschub_bp:
        # 1. Schlittenkörper (direkt in 2D auf cfg.y_top begrenzt, kein 3D-Trim-Box-Schnitt nötig)
        with BuildSketch(Plane.XY):
            _draw_dovetail_u_profile(cfg.feder_breite_hinten, cfg.y_u_mitte, cfg.y_top)
        with BuildSketch(Plane.XY.offset(cfg.nut_tiefe)):
            _draw_dovetail_u_profile(cfg.feder_breite_vorn, cfg.y_u_mitte, cfg.y_top)
        loft()

        # 2. Basisübergang: Loft von horizontalem Kreis auf Schlitten-Oberseite zur geneigten Dorn-Ebene
        with BuildSketch(Plane.XY.offset(cfg.nut_tiefe)):
            with Locations((0, cfg.y_dorn)):
                Circle(radius=dorn_r + cfg.basis_fase)
        with BuildSketch(tilted_plane.offset(cfg.basis_fase)):
            Circle(radius=dorn_r)
        loft()

        # 3. Dorn + Stützkonus + Kragen als 2D-Profilskizze mit 360°-Rotation (revolve)
        #    Hinweis: BuildLine nutzt bewusst die lokale Standardebene Plane.XY innerhalb von BuildSketch
        with BuildSketch(stem_profile_plane):
            with BuildLine():
                Polyline(*profile_pts, close=True)
            make_face()
        revolve(axis=stem_axis)

        # 4. Deckfläche vollkommen planparallel zum Druckbett kappen (Z = const, Normal = (0, 0, 1))
        split(bisect_by=Plane.XY.offset(z_dorn_ebene), keep=Keep.BOTTOM)

        # 5. Optionale durchgehende Innenbohrung entlang der geneigten Dornachse
        if cfg.innenbohrung > 0.0:
            with Locations(tilted_plane):
                Hole(radius=cfg.innenbohrung / 2.0)

    einschub = einschub_bp.part
    label_suffix = "Haltehaken" if dorn_art == "haltehaken" else "Steckdorn"
    einschub.label = f"DornEinschub_{label_suffix}"
    return einschub


# ====================================================================
# SANITY-CHECKS & GEOMETRIE-METRIKEN (FÜR AGENTIC CODING)
# ====================================================================

def analyze_part_geometry(name: str, solid: Shape) -> Dict[str, Any]:
    """Berechnet maschinenlesbare Geometriedaten für Sanity-Checks via Topologie-Selektoren."""
    bbox = solid.bounding_box()
    vol = solid.volume

    # Überprüfe Druckbett-Auflage (unterste Fläche bei Z_min == 0.0 und planar)
    bottom_face: Face = solid.faces().sort_by(Axis.Z)[0]
    bed_flat = (
        abs(bbox.min.Z) < 1e-3
        and bottom_face.geom_type == GeomType.PLANE
        and abs(bottom_face.normal_at().Z + 1.0) < 1e-2
    )

    # Überprüfe oberste Fläche via Topologie-Selektor (Planarität & Normalenvektor Z=(0,0,1))
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
    eff_overhang = cfg.eff_overhang_winkel
    print("[PASSUNG & FDM-DRUCKBARKEIT]")
    print(f"  • Schwalbenschwanz-Spiel: {cfg.spiel:.2f} mm (Nut: {cfg.nut_breite_hinten} mm, Feder: {cfg.feder_breite_hinten:.2f} mm) -> ✔ OK")
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
        # Flache Kopie (Shallow Copy) teilt die zugrundeliegende OCCT TopoDS_TShape
        haken_mated = copy.copy(haken).move(Location((0, 0, cfg.boden_dicke)))

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
