# Parametric CAD & 3D-Printing Workspace (`build123d`)

**[Live 3D Showcase & Parametric Customizer →](https://trampi.github.io/agentic-cad/)**

A generalized multi-project CAD workspace engineered for **Agentic Coding**, **support-free FDM 3D printing**, and **Autodesk Fusion STEP exchange**. Every project lives under `projects/<name>/` with its own living specification (`SPEC.md`), parametric Python model (`model.py`), build scripts (`generate.sh`, `clean.sh`), and generated artifacts (`build/`, `preview/`).

---

## Prerequisites

- Python 3.10+
- `build123d` and `Pillow`
- `openscad` (optional, used strictly as a headless renderer for multi-view preview PNGs)

```bash
pip install build123d pillow
```

---

## Repository Structure

- [`AGENTS.md`](AGENTS.md): Workspace guidelines, `SPEC.md`-synchronized iteration loop, and `build123d` modeling standards.
- [`template/`](template/): Canonical project template (`generate.sh`, `clean.sh`, `model.py`, `SPEC.md`, `README.md`).
- [`web/`](web/): Static Three.js + Pyodide (`OCP.wasm`) gallery & parametric 3D customizer frontend.
- [`scripts/build_site.py`](scripts/build_site.py): Static site builder emitting `_site/` for local preview (`--serve`) or GitHub Pages ([`.github/workflows/pages.yml`](.github/workflows/pages.yml)).
- [`.agents/skills/new-project/SKILL.md`](.agents/skills/new-project/SKILL.md): Skill for scaffolding and implementing new CAD projects from `template/`.
- `projects/`: Individual parametric CAD projects:
  - [`projects/hose_hook/`](projects/hose_hook/): Reference project — Universal Wall Mount & Quick-Release Hose Hook (`wall_mount`, `hose_hook`, `assembly`).
  - [`projects/remote_stand/`](projects/remote_stand/): Sculptural 4-slot couch-table stand for Light, Fire TV, LG, and Bose 3-2-1 remotes (`remote_stand`, `assembly`).

---

## Quickstart

### Build & Serve the Static Web Showcase (Gallery + Live 3D Customizer)

Live preview: <https://trampi.github.io/agentic-cad/>

```bash
# Build static gallery, default meshes, thumbnails, and parameter schemas into _site/
python3 scripts/build_site.py --out _site --serve
# Open http://127.0.0.1:8000/ in your browser
```

To include real-life photos of printed parts in the web showcase, add `.jpg`/`.png`/`.webp` images (plus an optional `captions.json` mapping filenames to captions) under `projects/<name>/photos/`. Keep raw photos stripped of EXIF metadata before committing; `build_site.py` also strips EXIF, auto-orients, and generates web thumbnails during the site build.

### Build an Existing Project (`projects/hose_hook`)
```bash
cd projects/hose_hook

# Full release build: STEP for Autodesk Fusion, STL for 3D printing, metrics.json & all previews
./generate.sh

# Fast iteration (STLs & Quad-Views in ~2-3s, skips STEP export)
./generate.sh --fast --part hose_hook --views quad

# Clean generated artifacts
./clean.sh
```

### Start a New Project
- **With an AI Agent**: Ask to create a new CAD project (triggers the `new-project` skill in `.agents/skills/new-project/SKILL.md`), which gathers requirements, copies `template/` into `projects/<new_name>/`, writes `SPEC.md`, implements `model.py`, and verifies the initial build.
- **Manually**:
  ```bash
  cp -r template projects/my_project
  cd projects/my_project
  ./generate.sh --fast --views quad
  ```
