#!/usr/bin/env python3
"""
Static Web Gallery & Parametric Customizer Site Builder.

Scans all projects under `projects/<name>/`, extracts parameter schemas from
`Config`, builds lightweight default tessellated meshes + isometric SVG
thumbnails via `build123d`, and bundles them with `web/` into a self-contained
static site (`_site/` by default) suitable for GitHub Pages or local serving.
"""

from __future__ import annotations

import argparse
import functools
import http.server
import importlib.util
import io
import json
import math
import re
import shutil
import socketserver
import struct
import sys
import zlib
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


ROOT_DIR = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT_DIR / "projects"
WEB_DIR = ROOT_DIR / "web"
PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
PHOTO_MAX_PX = 1600
PHOTO_THUMB_PX = 640


def _clean_markdown_text(text: str) -> str:
    """Strip basic markdown links, inline code, and LaTeX degrees for UI display."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\$([0-9.]+)\^\\circ\$", r"\1°", text)
    text = text.replace("`", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_project_docs(project_dir: Path) -> Dict[str, str]:
    """Extract display title and short summary from README.md (or SPEC.md fallback)."""
    slug = project_dir.name
    title = slug.replace("_", " ").title()
    summary = "Parametric build123d CAD project."

    for doc_name in ("README.md", "SPEC.md"):
        doc_path = project_dir / doc_name
        if not doc_path.is_file():
            continue
        lines = doc_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            if line.startswith("# "):
                raw_title = line[2:].strip()
                raw_title = re.sub(r"^Project Specification:\s*", "", raw_title)
                title = _clean_markdown_text(raw_title)
                break
        for line in lines:
            s = line.strip()
            if (
                not s
                or s.startswith("#")
                or s.startswith(">")
                or s.startswith("---")
                or s.startswith("|")
                or s.startswith("```")
                or s.startswith("-")
            ):
                continue
            summary = _clean_markdown_text(s)
            break
        if summary:
            break

    return {"title": title, "summary": summary}


def load_project_module(model_path: Path):
    """Import a project's model.py in isolation."""
    module_name = f"cad_project_{model_path.parent.name}"
    spec = importlib.util.spec_from_file_location(module_name, model_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {model_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def extract_param_schema(config_cls: Any) -> List[Dict[str, Any]]:
    """
    Build UI control schema from dataclass fields on `Config`.
    Fields annotated with `metadata` take priority; if no fields have UI
    metadata, numeric/bool fields are auto-exposed with safe bounds.
    """
    if not is_dataclass(config_cls):
        return []

    all_fields = list(fields(config_cls))
    has_explicit_meta = any(bool(f.metadata) for f in all_fields)
    schema: List[Dict[str, Any]] = []

    for f in all_fields:
        meta = dict(f.metadata) if f.metadata else {}
        if has_explicit_meta and not meta:
            continue

        default_val = f.default
        if isinstance(default_val, bool):
            ctrl_type = "boolean"
        elif "choices" in meta:
            ctrl_type = "select"
        elif isinstance(default_val, int):
            ctrl_type = "integer"
        elif isinstance(default_val, float):
            ctrl_type = "number"
        else:
            continue

        entry: Dict[str, Any] = {
            "key": f.name,
            "label": meta.get("label", f.name.replace("_", " ").title()),
            "type": ctrl_type,
            "default": default_val,
            "group": meta.get("group", "Parameters"),
        }
        if "unit" in meta:
            entry["unit"] = meta["unit"]
        if "cli" in meta:
            entry["cli"] = meta["cli"]

        if ctrl_type == "select":
            entry["choices"] = list(meta["choices"])
        elif ctrl_type in ("number", "integer"):
            span = abs(default_val) if abs(default_val) > 1e-6 else 10.0
            default_min = 0.0 if default_val >= 0 else round(default_val * 2.0, 2)
            default_max = round(max(span * 2.0, default_val + 20.0), 2)
            entry["min"] = meta.get("min", default_min)
            entry["max"] = meta.get("max", default_max)
            entry["step"] = meta.get("step", 1 if ctrl_type == "integer" else 0.5)

        schema.append(entry)

    return schema


def fallback_web_parts(module: Any, cfg: Any) -> List[Dict[str, Any]]:
    """Fallback builder if a model.py has not defined `build_web_parts` yet."""
    if hasattr(module, "build_web_parts"):
        return module.build_web_parts(cfg)

    parts = []
    for attr in dir(module):
        if attr.startswith("create_") and callable(getattr(module, attr)):
            part_name = attr.removeprefix("create_")
            try:
                res = getattr(module, attr)(cfg)
            except TypeError:
                continue
            if hasattr(res, "tessellate"):
                parts.append(
                    {
                        "name": part_name,
                        "shape": res,
                        "color": (0.25, 0.45, 0.75),
                        "opacity": 1.0,
                        "printable": True,
                        "assembly_offset": (0.0, 0.0, 0.0),
                        "exploded_offset": (0.0, 0.0, 0.0),
                    }
                )
    return parts


def tessellate_parts_to_binary(
    parts: List[Dict[str, Any]], tolerance: float = 0.2
) -> Tuple[bytes, List[Dict[str, Any]], List[Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]], Tuple[float, float, float], float]]]:
    """
    Tessellate all parts into a single packed little-endian binary stream
    (Float32 positions + Uint32 indices per part) and return metadata + raw tris.
    """
    chunks: List[bytes] = []
    part_metas: List[Dict[str, Any]] = []
    render_inputs = []

    for item in parts:
        shape = item["shape"]
        verts, tris = shape.tessellate(tolerance)
        flat_verts = [coord for v in verts for coord in (float(v.X), float(v.Y), float(v.Z))]
        flat_tris = [idx for tri in tris for idx in (int(tri[0]), int(tri[1]), int(tri[2]))]

        chunks.append(struct.pack(f"<{len(flat_verts)}f", *flat_verts))
        chunks.append(struct.pack(f"<{len(flat_tris)}I", *flat_tris))

        asm_off = [float(x) for x in item.get("assembly_offset", (0.0, 0.0, 0.0))]
        exp_off = [float(x) for x in item.get("exploded_offset", asm_off)]
        color = [float(c) for c in item.get("color", (0.25, 0.45, 0.75))]
        opacity = float(item.get("opacity", 1.0))

        part_metas.append(
            {
                "name": item["name"],
                "color": color,
                "opacity": opacity,
                "printable": bool(item.get("printable", True)),
                "assembly_offset": asm_off,
                "exploded_offset": exp_off,
                "vertex_count": len(verts),
                "index_count": len(flat_tris),
            }
        )

        shifted_verts = [(v.X + asm_off[0], v.Y + asm_off[1], v.Z + asm_off[2]) for v in verts]
        render_inputs.append((shifted_verts, tris, tuple(color), opacity))

    return b"".join(chunks), part_metas, render_inputs


def _encode_png_rgb(width: int, height: int, rgb_bytes: bytearray) -> bytes:
    """Encode an RGB byte buffer (width * height * 3) as a standard PNG."""
    stride = width * 3
    raw_rows = bytearray()
    for y in range(height):
        raw_rows.append(0)  # Filter type 0 (None)
        start = y * stride
        raw_rows.extend(rgb_bytes[start : start + stride])

    def chunk(tag: bytes, data: bytes) -> bytes:
        body = tag + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes(raw_rows), level=6)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def render_isometric_png(
    render_inputs: List[Tuple[List[Tuple[float, float, float]], List[Tuple[int, int, int]], Tuple[float, float, float], float]],
    width: int = 480,
    height: int = 340,
) -> bytes:
    """
    Render a lightweight shaded isometric PNG thumbnail directly from tessellated
    triangles using a pure-Python Z-buffer (zero external binary dependencies).
    """
    # Subtle dark radial gradient background matching web gallery cards
    rgb = bytearray(width * height * 3)
    cx_bg, cy_bg = width * 0.5, height * 0.45
    max_r = math.hypot(width * 0.65, height * 0.65)
    for y in range(height):
        dy = y - cy_bg
        row_off = y * width * 3
        for x in range(width):
            t = min(1.0, math.hypot(x - cx_bg, dy) / max_r)
            idx = row_off + x * 3
            rgb[idx] = int(30 - 15 * t)
            rgb[idx + 1] = int(41 - 18 * t)
            rgb[idx + 2] = int(59 - 17 * t)

    zbuf = [-1e30] * (width * height)

    az = math.radians(36.0)
    el = math.radians(28.0)
    cos_a, sin_a = math.cos(az), math.sin(az)
    cos_e, sin_e = math.cos(el), math.sin(el)

    right = (cos_a, sin_a, 0.0)
    to_cam = (sin_a * cos_e, -cos_a * cos_e, sin_e)
    up = (
        to_cam[1] * right[2] - to_cam[2] * right[1],
        to_cam[2] * right[0] - to_cam[0] * right[2],
        to_cam[0] * right[1] - to_cam[1] * right[0],
    )

    lx, ly, lz = -0.35, 0.55, 0.76
    l_norm = math.sqrt(lx * lx + ly * ly + lz * lz)
    lx, ly, lz = lx / l_norm, ly / l_norm, lz / l_norm

    def project(pt: Tuple[float, float, float]) -> Tuple[float, float, float]:
        x, y, z = pt
        return (
            x * right[0] + y * right[1] + z * right[2],
            x * up[0] + y * up[1] + z * up[2],
            x * to_cam[0] + y * to_cam[1] + z * to_cam[2],
        )

    min_x = float("inf")
    max_x = float("-inf")
    min_y = float("inf")
    max_y = float("-inf")

    projected_parts = []
    for verts, tris, color, opacity in render_inputs:
        pverts = [project(v) for v in verts]
        for px, py, _ in pverts:
            if px < min_x: min_x = px
            if px > max_x: max_x = px
            if py < min_y: min_y = py
            if py > max_y: max_y = py
        projected_parts.append((pverts, tris, color, opacity))

    if max_x <= min_x or max_y <= min_y:
        return _encode_png_rgb(width, height, rgb)

    pad = 28.0
    scale = min((width - 2 * pad) / (max_x - min_x), (height - 2 * pad) / (max_y - min_y))
    cx = (min_x + max_x) / 2.0
    cy = (min_y + max_y) / 2.0

    def to_screen(p: Tuple[float, float, float]) -> Tuple[float, float, float]:
        return (
            width * 0.5 + (p[0] - cx) * scale,
            height * 0.5 - (p[1] - cy) * scale,
            p[2],
        )

    def raster_tri(s0, s1, s2, cr, cg, cb, alpha, seen_mask=None):
        x0, y0, z0 = s0
        x1, y1, z1 = s1
        x2, y2, z2 = s2
        # Screen-space area (y points down, so front-facing has negative 2D signed area)
        area = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)
        if area >= -1e-5:
            return
        inv_area = 1.0 / area
        bx0 = max(0, int(math.floor(min(x0, x1, x2))))
        bx1 = min(width - 1, int(math.ceil(max(x0, x1, x2))))
        by0 = max(0, int(math.floor(min(y0, y1, y2))))
        by1 = min(height - 1, int(math.ceil(max(y0, y1, y2))))
        if bx1 < bx0 or by1 < by0:
            return

        for py in range(by0, by1 + 1):
            cy_px = py + 0.5
            row_idx = py * width
            for px in range(bx0, bx1 + 1):
                cx_px = px + 0.5
                w0 = ((x1 - cx_px) * (y2 - cy_px) - (y1 - cy_px) * (x2 - cx_px)) * inv_area
                w1 = ((x2 - cx_px) * (y0 - cy_px) - (y2 - cy_px) * (x0 - cx_px)) * inv_area
                w2 = 1.0 - w0 - w1
                if w0 < -1e-6 or w1 < -1e-6 or w2 < -1e-6:
                    continue
                pz = w0 * z0 + w1 * z1 + w2 * z2
                pidx = row_idx + px
                if pz > zbuf[pidx]:
                    off = pidx * 3
                    if alpha >= 0.99:
                        zbuf[pidx] = pz
                        rgb[off] = cr
                        rgb[off + 1] = cg
                        rgb[off + 2] = cb
                    else:
                        if seen_mask is not None:
                            if seen_mask[pidx]:
                                continue
                            seen_mask[pidx] = 1
                        inv_a = 1.0 - alpha
                        rgb[off] = int(rgb[off] * inv_a + cr * alpha)
                        rgb[off + 1] = int(rgb[off + 1] * inv_a + cg * alpha)
                        rgb[off + 2] = int(rgb[off + 2] * inv_a + cb * alpha)

    # Render opaque solids first, then translucent overlays sorted back-to-front
    opaque_parts = [p for p in projected_parts if p[3] >= 0.99]
    trans_parts = [p for p in projected_parts if p[3] < 0.99]

    for pverts, tris, color, opacity in opaque_parts:
        sverts = [to_screen(p) for p in pverts]
        for i0, i1, i2 in tris:
            p0, p1, p2 = pverts[i0], pverts[i1], pverts[i2]
            ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
            vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            if nz <= 1e-6:
                continue
            n_len = math.sqrt(nx * nx + ny * ny + nz * nz)
            if n_len <= 1e-9:
                continue
            diffuse = max(0.0, (nx * lx + ny * ly + nz * lz) / n_len)
            shade = 0.36 + 0.64 * diffuse
            cr = min(255, max(0, int(color[0] * 255 * shade)))
            cg = min(255, max(0, int(color[1] * 255 * shade)))
            cb = min(255, max(0, int(color[2] * 255 * shade)))
            raster_tri(sverts[i0], sverts[i1], sverts[i2], cr, cg, cb, 1.0)

    trans_tris = []
    trans_masks = [bytearray(width * height) for _ in trans_parts]
    for part_idx, (pverts, tris, color, opacity) in enumerate(trans_parts):
        sverts = [to_screen(p) for p in pverts]
        mask = trans_masks[part_idx]
        for i0, i1, i2 in tris:
            p0, p1, p2 = pverts[i0], pverts[i1], pverts[i2]
            ux, uy, uz = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
            vx, vy, vz = p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2]
            nx = uy * vz - uz * vy
            ny = uz * vx - ux * vz
            nz = ux * vy - uy * vx
            if nz <= 1e-6:
                continue
            n_len = math.sqrt(nx * nx + ny * ny + nz * nz)
            if n_len <= 1e-9:
                continue
            diffuse = max(0.0, (nx * lx + ny * ly + nz * lz) / n_len)
            shade = 0.42 + 0.58 * diffuse
            cr = min(255, max(0, int(color[0] * 255 * shade)))
            cg = min(255, max(0, int(color[1] * 255 * shade)))
            cb = min(255, max(0, int(color[2] * 255 * shade)))
            depth = (p0[2] + p1[2] + p2[2]) / 3.0
            trans_tris.append((depth, sverts[i0], sverts[i1], sverts[i2], cr, cg, cb, opacity, mask))

    trans_tris.sort(key=lambda t: t[0])
    for _, s0, s1, s2, cr, cg, cb, opacity, mask in trans_tris:
        raster_tri(s0, s1, s2, cr, cg, cb, opacity, seen_mask=mask)

    return _encode_png_rgb(width, height, rgb)


def _humanize_photo_caption(filename: str) -> str:
    """Derive a clean fallback caption from a photo filename."""
    stem = Path(filename).stem
    stem = re.sub(r"^\d+[_-]+", "", stem)
    text = re.sub(r"[_-]+", " ", stem).strip()
    if not text:
        return Path(filename).stem
    return text[0].upper() + text[1:]


def _load_photo_captions(photos_dir: Path) -> Dict[str, str]:
    """Load optional captions mapping from photos/captions.json."""
    captions_path = photos_dir / "captions.json"
    if not captions_path.is_file():
        return {}
    try:
        data = json.loads(captions_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items() if isinstance(v, str)}
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  ! Warning: ignoring invalid {captions_path.name}: {exc}")
    return {}


def _strip_and_resize_photo(
    src_path: Path,
    out_photos: Path,
    base_stem: str,
) -> Tuple[str, str]:
    """
    EXIF-transpose, strip all metadata, convert to sRGB, and emit web-sized
    full (`<= PHOTO_MAX_PX`) and thumbnail (`<= PHOTO_THUMB_PX`) images.
    Falls back to copying verbatim when Pillow cannot decode the file.
    """
    try:
        from PIL import Image, ImageCms, ImageOps
    except ImportError:
        dest = out_photos / src_path.name
        shutil.copy2(src_path, dest)
        return src_path.name, src_path.name

    try:
        with Image.open(src_path) as im:
            im = ImageOps.exif_transpose(im)
            has_alpha = im.mode in ("RGBA", "LA") or (
                im.mode == "P" and "transparency" in im.info
            )
            src_ext = src_path.suffix.lower()

            if has_alpha:
                clean = Image.frombytes("RGBA", im.size, im.convert("RGBA").tobytes())
                out_ext = ".webp" if src_ext == ".webp" else ".png"
                save_fmt = "WEBP" if out_ext == ".webp" else "PNG"
            else:
                rgb = im.convert("RGB")
                icc = im.info.get("icc_profile")
                if icc:
                    try:
                        src_prof = ImageCms.ImageCmsProfile(io.BytesIO(icc))
                        srgb_prof = ImageCms.createProfile("sRGB")
                        rgb = ImageCms.profileToProfile(
                            rgb, src_prof, srgb_prof, outputMode="RGB"
                        )
                    except Exception:
                        pass
                clean = Image.frombytes("RGB", rgb.size, rgb.tobytes())
                out_ext = ".webp" if src_ext == ".webp" else ".jpg"
                save_fmt = "WEBP" if out_ext == ".webp" else "JPEG"

            resample = getattr(Image, "Resampling", Image).LANCZOS

            def _save(img: Any, dest: Path, quality: int):
                if save_fmt == "JPEG":
                    img.save(dest, format="JPEG", quality=quality, optimize=True, progressive=True)
                elif save_fmt == "WEBP":
                    img.save(dest, format="WEBP", quality=quality, method=4)
                else:
                    img.save(dest, format="PNG", optimize=True)

            full_name = f"{base_stem}{out_ext}"
            full_img = clean.copy()
            if max(full_img.size) > PHOTO_MAX_PX:
                full_img.thumbnail((PHOTO_MAX_PX, PHOTO_MAX_PX), resample)
            _save(full_img, out_photos / full_name, quality=88)

            if max(full_img.size) > PHOTO_THUMB_PX:
                thumb_name = f"{base_stem}_thumb{out_ext}"
                thumb_img = full_img.copy()
                thumb_img.thumbnail((PHOTO_THUMB_PX, PHOTO_THUMB_PX), resample)
                _save(thumb_img, out_photos / thumb_name, quality=82)
            else:
                thumb_name = full_name

            return full_name, thumb_name
    except Exception as exc:
        print(f"  ! Warning: could not optimize photo '{src_path.name}' ({exc}); copying raw file.")
        dest = out_photos / src_path.name
        shutil.copy2(src_path, dest)
        return src_path.name, src_path.name


def discover_and_bundle_photos(project_dir: Path, proj_out: Path) -> List[Dict[str, str]]:
    """Discover real-life photos under `projects/<slug>/photos/` and bundle them."""
    photos_dir = project_dir / "photos"
    if not photos_dir.is_dir():
        return []

    photo_files = sorted(
        (p for p in photos_dir.iterdir() if p.is_file() and p.suffix.lower() in PHOTO_EXTENSIONS),
        key=lambda p: p.name.lower(),
    )
    if not photo_files:
        return []

    slug = project_dir.name
    captions = _load_photo_captions(photos_dir)
    out_photos = proj_out / "photos"
    out_photos.mkdir(parents=True, exist_ok=True)

    used_stems: set[str] = set()
    bundled: List[Dict[str, str]] = []
    for src_path in photo_files:
        base_stem = src_path.stem
        if base_stem in used_stems:
            idx = 2
            while f"{base_stem}_{idx}" in used_stems:
                idx += 1
            base_stem = f"{base_stem}_{idx}"
        used_stems.add(base_stem)

        full_name, thumb_name = _strip_and_resize_photo(src_path, out_photos, base_stem)
        caption = captions.get(src_path.name, _humanize_photo_caption(src_path.name))
        bundled.append(
            {
                "url": f"projects/{slug}/photos/{full_name}",
                "thumb_url": f"projects/{slug}/photos/{thumb_name}",
                "caption": caption,
            }
        )

    return bundled


def build_project_bundle(project_dir: Path, out_dir: Path) -> Dict[str, Any]:
    """Generate static viewer assets and default mesh data for one project."""
    slug = project_dir.name
    model_path = project_dir / "model.py"
    proj_out = out_dir / "projects" / slug
    proj_out.mkdir(parents=True, exist_ok=True)

    docs = extract_project_docs(project_dir)
    module = load_project_module(model_path)
    cfg = module.Config()
    schema = extract_param_schema(module.Config)

    parts = fallback_web_parts(module, cfg)
    mesh_bytes, part_metas, svg_inputs = tessellate_parts_to_binary(parts, tolerance=0.2)

    metrics = []
    if hasattr(module, "analyze_part_geometry"):
        for item in parts:
            if item.get("printable", True):
                metrics.append(module.analyze_part_geometry(item["name"], item["shape"]))

    # Write static files into project output folder
    shutil.copy2(model_path, proj_out / "model.py")
    spec_path = project_dir / "SPEC.md"
    has_spec = spec_path.is_file()
    if has_spec:
        shutil.copy2(spec_path, proj_out / "SPEC.md")

    (proj_out / "default_mesh.bin").write_bytes(mesh_bytes)

    thumb_rel = f"projects/{slug}/thumb.png"
    (proj_out / "thumb.png").write_bytes(render_isometric_png(svg_inputs))

    photos = discover_and_bundle_photos(project_dir, proj_out)

    project_manifest = {
        "slug": slug,
        "title": docs["title"],
        "summary": docs["summary"],
        "has_spec": has_spec,
        "thumb": thumb_rel,
        "photos": photos,
        "model_url": f"projects/{slug}/model.py",
        "mesh_url": f"projects/{slug}/default_mesh.bin",
        "schema": schema,
        "default_config": asdict(cfg),
        "parts": part_metas,
        "metrics": metrics,
        "extra_deps": list(getattr(module, "WEB_EXTRA_DEPS", [])),
    }
    (proj_out / "manifest.json").write_text(
        json.dumps(project_manifest, indent=2), encoding="utf-8"
    )

    printable_count = sum(1 for p in part_metas if p["printable"])
    total_vol_cm3 = round(sum(m.get("volume_mm3", 0.0) for m in metrics) / 1000.0, 1)
    primary_bbox = metrics[0]["bbox"] if metrics else {}

    return {
        "slug": slug,
        "title": docs["title"],
        "summary": docs["summary"],
        "thumb": thumb_rel,
        "photos": photos,
        "printable_parts": printable_count,
        "param_count": len(schema),
        "volume_cm3": total_vol_cm3,
        "bbox": primary_bbox,
    }


def build_site(out_dir: Path) -> Path:
    """Build the complete static site into `out_dir`."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Copy shared web frontend
    if not WEB_DIR.is_dir():
        raise FileNotFoundError(f"Missing shared web frontend directory: {WEB_DIR}")
    for item in WEB_DIR.iterdir():
        target = out_dir / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)

    # Build project bundles
    project_cards: List[Dict[str, Any]] = []
    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        if not (project_dir / "model.py").is_file():
            continue
        print(f"• Building static bundle for project '{project_dir.name}'...")
        card = build_project_bundle(project_dir, out_dir)
        project_cards.append(card)
        print(
            f"  ✓ {card['slug']}: {card['param_count']} controls, "
            f"{card['printable_parts']} printable part(s), {card['volume_cm3']} cm³, "
            f"{len(card['photos'])} photo(s)"
        )

    site_manifest = {
        "repo_title": "Parametric CAD Showcase",
        "repo_subtitle": "Single-source Python (build123d) models — instant 3D preview & client-side WASM customizer.",
        "projects": project_cards,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(site_manifest, indent=2), encoding="utf-8"
    )
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    print(f"\n✔ Static site built in '{out_dir}/' ({len(project_cards)} projects)")
    return out_dir


def serve_directory(directory: Path, port: int):
    """Serve the built static site over local HTTP for previewing."""
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(directory))
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Serving '{directory}/' at http://localhost:{port}/ (or http://127.0.0.1:{port}/) (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped server.")


def main():
    parser = argparse.ArgumentParser(
        description="Build static GitHub Pages gallery & parametric 3D viewer."
    )
    parser.add_argument("--out", default="_site", help="Output directory (default: _site)")
    parser.add_argument("--serve", action="store_true", help="Start local HTTP server after build")
    parser.add_argument("--port", type=int, default=8000, help="HTTP server port (default: 8000)")
    args = parser.parse_args()

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT_DIR / out_dir

    build_site(out_dir)
    if args.serve:
        serve_directory(out_dir, args.port)


if __name__ == "__main__":
    main()
