// ====================================================================
// Abnehmbare Halteplatte mit Dorn für Schläuche (Universal-Stecksystem)
// 2-teilig: Feste Wandhalterung für Schrank + abnehmbarer Dorn-Schlitten
// ====================================================================

/* [Darstellung / Druckauswahl] */
// Was soll gerendert werden:
// "zusammenbau"     = Gesteckter Zustand (Einsatzbereit am Schrank)
// "explosion"       = Explosionsansicht (Dorn angehoben zum Zeigen des Steckprinzips)
// "beide"           = Beide Teile nebeneinander für den 3D-Drucker
// "wandhalterung"   = Nur die Halterung für den Schrank
// "dorn_einschub"   = Nur der abnehmbare Dorn mit Schlitten
ansicht = "explosion"; // [zusammenbau, explosion, beide, wandhalterung, dorn_einschub]

/* [Passung & Toleranz] */
// Drucktoleranz / Gleitspiel zwischen Führung und Schlitten (mm)
spiel = 0.35; // [0.2:0.05:0.6]

/* [Dorn-Parameter (Schlauchanschluss)] */
// Art des Dorns:
// "steckdorn"  = Schlauch wird direkt aufgesteckt (mit Haltewülsten / Barbs)
// "haltehaken" = Schlauch wird aufgehängt (mit Sicherungskragen / Flansch)
dorn_art = "haltehaken"; // [steckdorn, haltehaken]

// Außendurchmesser des Dorns in mm (beim Steckdorn = Schlauch-Innendurchmesser)
dorn_durchmesser = 16;  // [6:0.5:50]

// Nutzlänge des Dorns in mm
dorn_laenge = 50;       // [20:1:120]

// Neigungswinkel des Dorns nach oben in Grad (verhindert Abrutschen)
dorn_neigung = 5;       // [0:1:20]

// Radius/Breite der Verstärkungsfase an der Basis in mm
basis_fase = 5;         // [1:0.5:12]

// Anzahl der Halterippen / Barbs (nur bei dorn_art = "steckdorn")
barb_anzahl = 3;        // [0:1:6]

// Übermaß der Halterippen (Radius-Zuwachs in mm)
barb_hoehe = 1.2;       // [0.3:0.1:3.0]

// Länge einer einzelnen Halterippe in mm
barb_laenge = 7;        // [3:1:15]

// Fasenlänge an der Spitze für leichtes Ansetzen (mm)
spitzen_anfasung = 4;   // [1:0.5:10]

/* [Haltehaken-Details (nur bei dorn_art = "haltehaken")] */
// Durchmesser des vorderen Sicherungskragens in mm
kragen_durchmesser = 24;// [10:1:60]

// Dicke des zylindrischen Kragenrandes in mm
kragen_dicke = 4;       // [2:1:15]

// Steigungswinkel der Stützfase unter dem Kragen zur Horizontalen in Grad
// 50° garantiert selbst mit der 5° Neigung supportfreies Drucken (< 45° Überhang zum Bett)
kragen_fase_winkel = 50;// [45:1:65]

// Optionale Innenbohrung durch den Dorn (0 = massiv)
innenbohrung = 0;       // [0:0.5:40]

/* [Wandhalterung (Montage am Schrank)] */
// Gesamtbreite der Wandhalterung in mm
halter_breite = 50;     // [40:1:90]

// Gesamthöhe der Wandhalterung in mm
halter_hoehe = 70;      // [45:1:150]

// Gesamtdicke / Tiefe der Wandhalterung in mm
halter_tiefe = 12;      // [9:1:22]

// Wandstärke des Bodens hinter der Führungsnut in mm
boden_dicke = 4;        // [3:0.5:8]

// Eckenverrundung der Halterung in mm
halter_radius = 4;      // [1:0.5:10]

/* [Schwalbenschwanz-Führung] */
// Nutbreite am Nutgrund (breite Rückseite) in mm
nut_breite_hinten = 36; // [22:1:60]

// Nutbreite an der Oberfläche (schmale Vorderseite) in mm
nut_breite_vorn = 30;   // [18:1:50]

/* [Schraubenlöcher (2 Stück zur Schrankmontage)] */
// Schaftdurchmesser der Schraube in mm (z. B. 4.0 für Holzschrauben / M4)
schraube_durchmesser = 4.2;  // [2.5:0.1:6.0]

// Senkkopfdurchmesser in mm
senkkopf_durchmesser = 8.2; // [4.0:0.1:12.0]

// Senkwinkel in Grad (Standard 90° DIN 7997)
senkkopf_winkel = 90;       // [60:1:120]

// Y-Position der oberen Schraube (relativ zur Mitte) in mm
schraube_oben_y = 16;       // [5:1:35]

// Y-Position der unteren Schraube (relativ zur Mitte) in mm
schraube_unten_y = -14;     // [-35:1:-5]

/* [Qualität] */
$fn = 64;

// ====================================================================
// BERECHNUNGEN
// ====================================================================

nut_tiefe = halter_tiefe - boden_dicke;
dorn_radius = dorn_durchmesser / 2;
kragen_radius = kragen_durchmesser / 2;
schraube_radius = schraube_durchmesser / 2;
senkkopf_radius = senkkopf_durchmesser / 2;

// Y-Zentrum des unteren U-Bogens
y_u_mitte = -halter_hoehe / 2 + nut_breite_hinten / 2 + 4;
y_top = halter_hoehe / 2;
outer_len = y_top - y_u_mitte - halter_radius;
slot_laenge = halter_hoehe + 30;

// Senktiefe berechnen
senk_tiefe = (senkkopf_radius - schraube_radius) / tan(senkkopf_winkel / 2);

// ====================================================================
// MODULE: GEOMETRIE DER FÜHRUNGSNUT (SCHWALBENSCHWANZ U-SLOT)
// ====================================================================

// 2D U-Profil: Unten ein Halbkreis, nach oben ein gerader Schacht
module u_profil_2d(breite, laenge) {
    union() {
        circle(d = breite);
        translate([-breite / 2, 0])
            square([breite, laenge]);
    }
}

// 3D Schwalbenschwanz-Nut mit Verjüngung in X-Richtung (Gleitrichtung Y bleibt parallel)
module u_nut_3d(b_hinten, b_vorn, tiefe, laenge) {
    linear_extrude(height = tiefe, scale = [b_vorn / b_hinten, 1.0])
        u_profil_2d(b_hinten, laenge);
}

// ====================================================================
// MODULE: WANDHALTERUNG (FEST AM SCHRANK)
// ====================================================================

module schraubsenkung(pos_y) {
    // Schraube im Boden der Nut: Der Kopf wird bündig unter der Gleitfläche versenkt
    senk_tiefe_eff = min(boden_dicke - 1.2, senk_tiefe + 0.3);

    translate([0, pos_y, 0]) {
        // Durchgangsbohrung durch den Schrankboden
        translate([0, 0, -2])
            cylinder(r = schraube_radius, h = boden_dicke + 4);

        // Senkkopf (schließt bündig oder leicht vertieft im Nutboden ab)
        translate([0, 0, boden_dicke - senk_tiefe_eff])
            cylinder(r1 = schraube_radius, r2 = senkkopf_radius, h = senk_tiefe_eff + 0.05);

        // Zylindrischer Freistich nach oben durch die Führungsnut
        translate([0, 0, boden_dicke])
            cylinder(r = senkkopf_radius, h = nut_tiefe + 2);
    }
}

module wandhalterung() {
    difference() {
        // Äußerer U-Körper mit abgerundetem Boden
        translate([0, y_u_mitte, 0])
            linear_extrude(height = halter_tiefe)
                offset(r = halter_radius)
                    u_profil_2d(halter_breite - 2 * halter_radius, outer_len);

        // Schwalbenschwanz-Führungsnut (schneidet ab Z = boden_dicke glatt bis oben durch)
        translate([0, y_u_mitte, boden_dicke])
            u_nut_3d(nut_breite_hinten, nut_breite_vorn, nut_tiefe + 2, slot_laenge);

        // 2 Schraubenlöcher
        schraubsenkung(schraube_oben_y);
        schraubsenkung(schraube_unten_y);
    }
}

// ====================================================================
// MODULE: DORN MIT GLEITSCHLITTEN (ABNEHMBAR)
// ====================================================================

// Haltewulst für den Schlauch (Tannenzapfen-Widerhaken)
module halterippe() {
    rampen_laenge = barb_laenge * 0.75;
    kanten_laenge = barb_laenge * 0.25;

    union() {
        cylinder(r1 = dorn_radius, r2 = dorn_radius + barb_hoehe, h = kanten_laenge);
        translate([0, 0, kanten_laenge])
            cylinder(r1 = dorn_radius + barb_hoehe, r2 = dorn_radius, h = rampen_laenge);
    }
}

// Fugenloser Übergangskonus von der planen Schlittenfläche zum geneigten Dorn
module dorn_basis_uebergang() {
    hull() {
        // Untere ebene Basis: liegt exakt auf der Schlittenoberfläche (1mm versenkt)
        translate([0, 0, nut_tiefe - 1])
            cylinder(r = dorn_radius + basis_fase, h = 1);

        // Obere Scheibe: bereits um 5° geneigt auf Höhe basis_fase
        translate([0, 0, nut_tiefe])
            rotate([-dorn_neigung, 0, 0])
                translate([0, 0, basis_fase])
                    cylinder(r = dorn_radius, h = 0.1);
    }
}

// Geneigter Dornschaft
module dorn_schaft() {
    translate([0, 0, basis_fase]) {
        cylinder(r = dorn_radius, h = dorn_laenge - basis_fase);

        if (dorn_art == "steckdorn") {
            // Konische Einführspitze (reicht über die Schnittebene hinaus zur horizontalen Kappung)
            spitze_h = min(spitzen_anfasung, dorn_laenge * 0.2);
            translate([0, 0, dorn_laenge - basis_fase - spitze_h])
                cylinder(r1 = dorn_radius, r2 = max(2, dorn_radius * 0.65), h = spitze_h + 4);

            if (barb_anzahl > 0) {
                start_z = 3;
                nutz_bereich = dorn_laenge - basis_fase - spitze_h - 6;
                schritt = (barb_anzahl > 1) ? (nutz_bereich - barb_laenge) / (barb_anzahl - 1) : 0;
                for (i = [0 : barb_anzahl - 1]) {
                    z_pos = (barb_anzahl > 1) ? (start_z + i * schritt) : (start_z + nutz_bereich / 2);
                    translate([0, 0, z_pos])
                        halterippe();
                }
            }
        } else if (dorn_art == "haltehaken") {
            // Druckoptimierte Stützfase (50° Steigung) gegen Slicer-Überhänge
            kragen_delta_r = max(0.5, kragen_radius - dorn_radius);
            kragen_fase_h = kragen_delta_r * tan(kragen_fase_winkel);
            z_kragen = dorn_laenge - basis_fase - kragen_dicke;

            // 50°-Stützkonus unterhalb des Kragens
            translate([0, 0, z_kragen - kragen_fase_h])
                cylinder(r1 = dorn_radius, r2 = kragen_radius, h = kragen_fase_h);

            // Zylindrischer Kragenabschluss (reicht über die Schnittebene hinaus)
            translate([0, 0, z_kragen])
                cylinder(r = kragen_radius, h = kragen_dicke + 6);
        }
    }
}

// Der Schlittenkörper mit Dorn
module dorn_einschub() {
    b_h_m = nut_breite_hinten - 2 * spiel;
    b_v_m = nut_breite_vorn   - 2 * spiel;
    einschub_laenge = y_top - y_u_mitte;

    // Y-Position des Dorns auf dem Schlitten (optimiert für Biegesteifigkeit)
    y_dorn = y_u_mitte + einschub_laenge * 0.42;

    // Absolute Z-Höhe der horizontalen Stirnfläche (parallel zum Druckbett Z = 0)
    z_dorn_ebene = nut_tiefe + dorn_laenge * cos(dorn_neigung);

    difference() {
        union() {
            // Schlittenkörper (abzüglich Spiel, oben plan und bündig auf Höhe y_top abgeschlossen)
            intersection() {
                translate([-halter_breite, y_u_mitte - b_h_m, 0])
                    cube([halter_breite * 2, einschub_laenge + b_h_m, nut_tiefe]);

                translate([0, y_u_mitte, 0])
                    u_nut_3d(b_h_m, b_v_m, nut_tiefe, einschub_laenge + 5);
            }

            // Fugenloser Basisübergang zum Dorn
            translate([0, y_dorn, 0])
                dorn_basis_uebergang();

            // Geneigter Dorn
            translate([0, y_dorn, nut_tiefe])
                rotate([-dorn_neigung, 0, 0])
                    dorn_schaft();
        }

        // Planparalleles Ebnen der oberen Stirnfläche (exakt horizontal / parallel zum Druckbett)
        translate([-100, -100, z_dorn_ebene])
            cube([200, 200, 50]);

        // Optionale Innenbohrung
        if (innenbohrung > 0) {
            translate([0, y_dorn, nut_tiefe])
                rotate([-dorn_neigung, 0, 0])
                    translate([0, 0, -nut_tiefe - 2])
                        cylinder(r = innenbohrung / 2, h = dorn_laenge + nut_tiefe + 10);
        }
    }
}

// ====================================================================
// HAUPTAUSWAHL (SZENE)
// ====================================================================

if (ansicht == "wandhalterung") {
    color([1.0, 0.42, 0.05])
        wandhalterung();
}
else if (ansicht == "dorn_einschub") {
    color([0.25, 0.25, 0.28])
        dorn_einschub();
}
else if (ansicht == "beide") {
    color([1.0, 0.42, 0.05])
        translate([-halter_breite / 2 - 8, 0, 0])
            wandhalterung();

    color([0.25, 0.25, 0.28])
        translate([halter_breite / 2 + 8, 0, 0])
            dorn_einschub();
}
else if (ansicht == "zusammenbau") {
    color([1.0, 0.42, 0.05])
        wandhalterung();

    color([0.25, 0.25, 0.28])
        translate([0, 0, boden_dicke])
            dorn_einschub();
}
else if (ansicht == "explosion") {
    color([1.0, 0.42, 0.05])
        wandhalterung();

    color([0.25, 0.25, 0.28])
        translate([0, 25, boden_dicke + 15])
            dorn_einschub();
}
