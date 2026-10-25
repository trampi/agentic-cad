#!/usr/bin/env python3
"""
Parametrische Halteplatte mit Dorn für Schläuche (Universal-Stecksystem)
Modelliert mit build123d für hochpräzisen B-Rep / STEP-Export (z. B. für Autodesk Fusion)
"""

import math
from pathlib import Path
from build123d import *

# ====================================================================
# PARAMETER
# ====================================================================

# [Wandhalterung (Schrankmontage)]
HALTER_BREITE = 50.0       # Gesamtbreite der Wandhalterung (mm)
HALTER_HOEHE = 70.0        # Gesamthöhe der Wandhalterung (mm)
HALTER_TIEFE = 12.0        # Gesamtdicke / Tiefe der Wandhalterung (mm)
BODEN_DICKE = 4.0          # Wandstärke des Bodens hinter der Führungsnut (mm)
HALTER_RADIUS = 4.0        # Eckenverrundung der Halterung (mm)

# [Schwalbenschwanz-Führung]
NUT_BREITE_HINTEN = 36.0   # Nutbreite am Nutgrund (breite Rückseite) (mm)
NUT_BREITE_VORN = 30.0     # Nutbreite an der Oberfläche (schmale Vorderseite) (mm)
SPIEL = 0.35               # Gleitspiel zwischen Nut und Einschub (mm)

# [Schraubenlöcher (2 Stück im Schrankhalter)]
SCHRAUBE_DURCHMESSER = 4.2 # Schaftdurchmesser (z. B. M4 oder 4.0mm Holzschraube) (mm)
SENKKOPF_DURCHMESSER = 8.2 # Senkkopfdurchmesser an der Oberfläche (mm)
SENKKOPF_WINKEL = 90.0     # Senkwinkel in Grad (DIN 7997)
SCHRAUBE_OBEN_Y = 16.0     # Y-Position der oberen Schraube (mm)
SCHRAUBE_UNTEN_Y = -14.0   # Y-Position der unteren Schraube (mm)

# [Dorn-Parameter]
DORN_DURCHMESSER = 16.0    # Außendurchmesser des Dorns (mm)
DORN_LAENGE = 50.0         # Nutzlänge des Dorns (mm)
DORN_NEIGUNG = 5.0         # Neigungswinkel nach oben in Grad (verhindert Abrutschen)
BASIS_FASE = 5.0           # Breite/Höhe des Basis-Verstärkungskonus (mm)
INNENBOHRUNG = 0.0         # Innendurchmesser Bohrung (0 = massiv) (mm)

# [Steckdorn-Details]
BARB_ANZAHL = 3            # Anzahl der Haltewülste (Widerhaken)
BARB_HOEHE = 1.2           # Übermaß der Rippen (Radius-Zunahme in mm)
BARB_LAENGE = 7.0          # Länge einer einzelnen Halterippe (mm)
SPITZEN_ANFASUNG = 4.0     # Fasenlänge an der Einführspitze (mm)

# [Haltehaken-Details]
KRAGEN_DURCHMESSER = 24.0  # Durchmesser des Abschlusskragens (mm)
KRAGEN_DICKE = 4.0         # Dicke des Kragens (mm)
KRAGEN_FASE_WINKEL = 50.0  # Steigungswinkel der Stützfase unter dem Kragen (Grad)


# ====================================================================
# MODELLIERUNG: WANDHALTERUNG
# ====================================================================

def create_wandhalterung() -> Solid:
    """Erstellt die Wandhalterung mit Schwalbenschwanzführung und 2 Senkbohrungen."""
    nut_tiefe = HALTER_TIEFE - BODEN_DICKE
    y_u_mitte = -HALTER_HOEHE / 2.0 + NUT_BREITE_HINTEN / 2.0 + 4.0  # -13.0
    y_top = HALTER_HOEHE / 2.0                                      # 35.0

    # 1. Äußerer Grundkörper (U-förmig)
    w_inner = HALTER_BREITE - 2.0 * HALTER_RADIUS
    len_inner = y_top - y_u_mitte - HALTER_RADIUS
    c_outer = Pos(0, y_u_mitte) * Circle(radius=w_inner / 2.0)
    r_outer = Pos(0, y_u_mitte + len_inner / 2.0) * Rectangle(w_inner, len_inner)
    outer_sketch = offset(c_outer + r_outer, amount=HALTER_RADIUS)
    body = extrude(outer_sketch, amount=HALTER_TIEFE)

    # 2. Schwalbenschwanz-Führungsnut (Loft als Schnittwerkzeug)
    cutter_len = (y_top + 10.0) - y_u_mitte

    def groove_profile(w: float):
        c = Pos(0, y_u_mitte) * Circle(radius=w / 2.0)
        r = Pos(0, y_u_mitte + cutter_len / 2.0) * Rectangle(w, cutter_len)
        return c + r

    s_back = Pos(0, 0, BODEN_DICKE) * groove_profile(NUT_BREITE_HINTEN)
    s_front = Pos(0, 0, HALTER_TIEFE + 0.1) * groove_profile(NUT_BREITE_VORN)
    groove_cutter = loft([s_back, s_front])

    bracket = body - groove_cutter

    # 3. Zwei Senkbohrungen im Nutboden
    schraube_r = SCHRAUBE_DURCHMESSER / 2.0
    senk_r = SENKKOPF_DURCHMESSER / 2.0
    senk_tiefe_theo = (senk_r - schraube_r) / math.tan(math.radians(SENKKOPF_WINKEL / 2.0))
    senk_tiefe_eff = min(BODEN_DICKE - 1.2, senk_tiefe_theo + 0.3)
    z_cone_base = BODEN_DICKE - senk_tiefe_eff

    def screw_cutter(y_pos: float) -> Solid:
        through = Pos(0, y_pos, -2.0) * Cylinder(
            radius=schraube_r,
            height=BODEN_DICKE + 4.0,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        cone = Pos(0, y_pos, z_cone_base) * Cone(
            bottom_radius=schraube_r,
            top_radius=senk_r,
            height=senk_tiefe_eff,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        clearance = Pos(0, y_pos, BODEN_DICKE) * Cylinder(
            radius=senk_r,
            height=HALTER_TIEFE + 2.0,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        return through + cone + clearance

    bracket = bracket - screw_cutter(SCHRAUBE_OBEN_Y) - screw_cutter(SCHRAUBE_UNTEN_Y)
    bracket.label = "Wandhalterung"
    return bracket


# ====================================================================
# MODELLIERUNG: DORN-EINSCHUB (SCHLITTEN MIT DORN)
# ====================================================================

def create_dorn_einschub(dorn_art: str = "steckdorn") -> Solid:
    """
    Erstellt den abnehmbaren Gleitschlitten mit Dorn.
    dorn_art: "steckdorn" (mit Haltewülsten) oder "haltehaken" (mit 50°-Stützkragen).
    """
    nut_tiefe = HALTER_TIEFE - BODEN_DICKE
    y_u_mitte = -HALTER_HOEHE / 2.0 + NUT_BREITE_HINTEN / 2.0 + 4.0
    y_top = HALTER_HOEHE / 2.0
    cutter_len = (y_top + 10.0) - y_u_mitte

    b_h_m = NUT_BREITE_HINTEN - 2.0 * SPIEL
    b_v_m = NUT_BREITE_VORN - 2.0 * SPIEL

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
        HALTER_BREITE * 3.0, 100.0, nut_tiefe * 2.0
    )

    # 2. Dorn aufbauen
    dorn_r = DORN_DURCHMESSER / 2.0
    y_dorn = y_u_mitte + (y_top - y_u_mitte) * 0.42

    # Gekippte Arbeitsebene für den Dorn (um X-Achse geneigt)
    tilted_plane = Plane(
        origin=(0, y_dorn, nut_tiefe),
        x_dir=(1, 0, 0)
    ).rotated((-DORN_NEIGUNG, 0, 0))

    # 2a. Fugenloser Basis-Übergangskonus (plan auf der Schlittenoberfläche z=nut_tiefe)
    disk1 = Pos(0, y_dorn, nut_tiefe) * Circle(radius=dorn_r + BASIS_FASE)
    disk2 = tilted_plane.offset(BASIS_FASE) * Circle(radius=dorn_r)
    base_trans = loft([disk1, disk2])

    # 2b. Dornschaft
    shaft = tilted_plane.offset(BASIS_FASE) * Cylinder(
        radius=dorn_r,
        height=DORN_LAENGE - BASIS_FASE,
        align=(Align.CENTER, Align.CENTER, Align.MIN)
    )

    dorn_components = [base_trans, shaft]

    if dorn_art == "steckdorn":
        # Konische Einführspitze (reicht über Solllänge hinaus für plane Kappe)
        spitze_h = min(SPITZEN_ANFASUNG, DORN_LAENGE * 0.2)
        tip_start = DORN_LAENGE - spitze_h
        tip_cone = tilted_plane.offset(tip_start) * Cone(
            bottom_radius=dorn_r,
            top_radius=max(2.0, dorn_r * 0.65),
            height=spitze_h + 4.0,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        dorn_components.append(tip_cone)

        # Haltewülste (Barbs)
        if BARB_ANZAHL > 0:
            start_z = 3.0
            nutz_bereich = DORN_LAENGE - BASIS_FASE - spitze_h - 6.0
            schritt = (nutz_bereich - BARB_LAENGE) / (BARB_ANZAHL - 1) if BARB_ANZAHL > 1 else 0
            kanten_laenge = BARB_LAENGE * 0.25
            rampen_laenge = BARB_LAENGE * 0.75

            for i in range(BARB_ANZAHL):
                z_pos = BASIS_FASE + start_z + (i * schritt if BARB_ANZAHL > 1 else nutz_bereich / 2.0)
                cone_step = tilted_plane.offset(z_pos) * Cone(
                    bottom_radius=dorn_r,
                    top_radius=dorn_r + BARB_HOEHE,
                    height=kanten_laenge,
                    align=(Align.CENTER, Align.CENTER, Align.MIN)
                )
                cone_ramp = tilted_plane.offset(z_pos + kanten_laenge) * Cone(
                    bottom_radius=dorn_r + BARB_HOEHE,
                    top_radius=dorn_r,
                    height=rampen_laenge,
                    align=(Align.CENTER, Align.CENTER, Align.MIN)
                )
                dorn_components.extend([cone_step, cone_ramp])

    elif dorn_art == "haltehaken":
        kragen_r = KRAGEN_DURCHMESSER / 2.0
        kragen_delta_r = max(0.5, kragen_r - dorn_r)
        kragen_fase_h = kragen_delta_r * math.tan(math.radians(KRAGEN_FASE_WINKEL))
        z_kragen = DORN_LAENGE - BASIS_FASE - KRAGEN_DICKE

        # 50°-Stützkonus unterhalb des Kragens (druckbar ohne Support)
        support_cone = tilted_plane.offset(z_kragen - kragen_fase_h) * Cone(
            bottom_radius=dorn_r,
            top_radius=kragen_r,
            height=kragen_fase_h,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        # Zylindrischer Kragen (überstehend für horizontale Kappung)
        collar = tilted_plane.offset(z_kragen) * Cylinder(
            radius=kragen_r,
            height=KRAGEN_DICKE + 6.0,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        dorn_components.extend([support_cone, collar])

    # 3. Dorn-Komponenten verschmelzen
    dorn_solid = Compound(dorn_components).fuse()

    # 4. Stirnfläche planparallel zum Druckbett kappen (Z = const)
    z_dorn_ebene = nut_tiefe + DORN_LAENGE * math.cos(math.radians(DORN_NEIGUNG))
    dorn_leveled = split(dorn_solid, Plane.XY.offset(z_dorn_ebene), keep=Keep.BOTTOM)

    # 5. Schlitten und Dorn verbinden
    einschub = slider.fuse(dorn_leveled)

    # 6. Optionale Innenbohrung
    if INNENBOHRUNG > 0.0:
        bore_r = INNENBOHRUNG / 2.0
        bore = tilted_plane.offset(-nut_tiefe - 2.0) * Cylinder(
            radius=bore_r,
            height=DORN_LAENGE + nut_tiefe + 10.0,
            align=(Align.CENTER, Align.CENTER, Align.MIN)
        )
        einschub = einschub - bore

    einschub.label = f"DornEinschub_{dorn_art.capitalize()}"
    return einschub


# ====================================================================
# EXPORT-FUNKTIONEN FÜR STEP & STL
# ====================================================================

def export_all(output_dir: str = "."):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("build123d CAD Export -> STEP & STL")
    print("=" * 60)

    # 1. Wandhalterung generieren
    print("\n[1/4] Erzeuge Wandhalterung...")
    bracket = create_wandhalterung()
    step_bracket = out / "wandhalterung.step"
    export_step(bracket, str(step_bracket))
    print(f"  ✓ STEP exportiert: {step_bracket}")

    # 2. Dorn-Einschub: Steckdorn
    print("\n[2/4] Erzeuge Dorn-Einschub (Steckdorn mit Barbs)...")
    steckdorn = create_dorn_einschub("steckdorn")
    step_steck = out / "dorn_einschub_steckdorn.step"
    export_step(steckdorn, str(step_steck))
    print(f"  ✓ STEP exportiert: {step_steck}")

    # 3. Dorn-Einschub: Haltehaken
    print("\n[3/4] Erzeuge Dorn-Einschub (Haltehaken mit Stützkragen)...")
    haken = create_dorn_einschub("haltehaken")
    step_haken = out / "dorn_einschub_haltehaken.step"
    export_step(haken, str(step_haken))
    print(f"  ✓ STEP exportiert: {step_haken}")

    # 4. Baugruppen (Zusammenbau für Autodesk Fusion)
    print("\n[4/4] Erzeuge Baugruppen (Zusammenbau & Druckbett-Layout)...")
    # Gesteckter Zustand (Einschub um BODEN_DICKE in Z versetzt)
    steckdorn_mated = Pos(0, 0, BODEN_DICKE) * steckdorn
    haken_mated = Pos(0, 0, BODEN_DICKE) * haken

    assembly_steck = Compound([bracket, steckdorn_mated], label="Baugruppe_Steckdorn")
    assembly_haken = Compound([bracket, haken_mated], label="Baugruppe_Haltehaken")

    step_assy_steck = out / "baugruppe_steckdorn.step"
    step_assy_haken = out / "baugruppe_haltehaken.step"
    export_step(assembly_steck, str(step_assy_steck))
    export_step(assembly_haken, str(step_assy_haken))
    print(f"  ✓ Baugruppe STEP (Steckdorn): {step_assy_steck}")
    print(f"  ✓ Baugruppe STEP (Haltehaken): {step_assy_haken}")

    # Druckbett-Layout: Beide Teile nebeneinander flach auf Z=0
    layout_bracket = Pos(-HALTER_BREITE / 2.0 - 10.0, 0, 0) * bracket
    layout_dorn = Pos(HALTER_BREITE / 2.0 + 10.0, 0, 0) * steckdorn
    druckbett_layout = Compound([layout_bracket, layout_dorn], label="Druckbett_Layout")

    step_druckbett = out / "beide_druckbett.step"
    export_step(druckbett_layout, str(step_druckbett))
    print(f"  ✓ Druckbett-Layout STEP: {step_druckbett}")

    # Optional STL-Export für direkten 3D-Druck
    stl_bracket = out / "wandhalterung_b3d.stl"
    stl_steck = out / "dorn_einschub_steckdorn_b3d.stl"
    export_stl(bracket, str(stl_bracket))
    export_stl(steckdorn, str(stl_steck))
    print(f"  ✓ STL exportiert: {stl_bracket}")
    print(f"  ✓ STL exportiert: {stl_steck}")

    print("\n" + "=" * 60)
    print("Alle STEP-Dateien erfolgreich für Autodesk Fusion exportiert!")
    print("=" * 60)


if __name__ == "__main__":
    export_all(".")
