import { CadViewer, buildBinaryStlFromMesh } from "./viewer.js";

function getQueryParams() {
  const sp = new URLSearchParams(window.location.search);
  return {
    slug: sp.get("project"),
    pyodideVersion: sp.get("pyodide") || "v314.0.7",
  };
}

let { slug: projectSlug, pyodideVersion } = getQueryParams();

const galleryView = document.getElementById("gallery-view");
const workspaceView = document.getElementById("workspace-view");

let viewer = null;
let projectManifest = null;
let currentParams = {};
let currentParts = [];
let hasUnsavedCustomParams = false;
let lastBuildFromWasm = false;
let galleryLoaded = false;
let toolbarWired = false;
let lightboxWired = false;
let activeViewToken = 0;

let lightboxPhotos = [];
let lightboxIndex = 0;
let lightboxReturnFocus = null;

let worker = null;
let kernelReady = false;
let kernelInitializing = false;
let buildInFlight = false;
let pendingBuild = false;
let debounceTimer = null;
let reqCounter = 0;
const pendingRequests = new Map();

function isModifiedClick(event) {
  return event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0;
}

function renderFatalError(err) {
  console.error(err);
  document.body.innerHTML = `<div style="padding:32px;font-family:sans-serif;color:#f87171;">
    <h2>Failed to load CAD preview</h2>
    <pre>${escapeHtml(err?.stack || err?.message || String(err))}</pre>
    <p><a href="./" style="color:#38bdf8;">Back to project gallery</a></p>
  </div>`;
}

function navigateTo(slug) {
  const url = slug ? `?project=${encodeURIComponent(slug)}` : "./";
  window.history.pushState({ project: slug || null }, "", url);
  routeToCurrentLocation().catch(renderFatalError);
}

async function routeToCurrentLocation() {
  const q = getQueryParams();
  projectSlug = q.slug;
  pyodideVersion = q.pyodideVersion;
  if (projectSlug) {
    await initWorkspace(projectSlug);
  } else {
    await initGallery();
  }
}

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function assetUrl(relPath) {
  return `./${encodeURI(String(relPath || ""))}`;
}

// ====================================================================
// SHARED LIGHTBOX MODAL
// ====================================================================

function renderLightboxFrame() {
  const photo = lightboxPhotos[lightboxIndex];
  if (!photo) return;
  const img = document.getElementById("lightbox-img");
  const captionEl = document.getElementById("lightbox-caption");
  const counterEl = document.getElementById("lightbox-counter");
  const prevBtn = document.getElementById("lightbox-prev-btn");
  const nextBtn = document.getElementById("lightbox-next-btn");

  img.src = assetUrl(photo.url);
  img.alt = photo.caption || "Printed part photo";
  captionEl.textContent = photo.caption || "";
  captionEl.classList.toggle("hidden", !photo.caption);
  counterEl.textContent = `${lightboxIndex + 1} / ${lightboxPhotos.length}`;

  const hasMulti = lightboxPhotos.length > 1;
  prevBtn.classList.toggle("hidden", !hasMulti);
  nextBtn.classList.toggle("hidden", !hasMulti);
}

function openLightbox(photos, startIndex = 0) {
  if (!photos || photos.length === 0) return;
  wireLightboxOnce();
  lightboxReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  lightboxPhotos = photos;
  lightboxIndex = ((startIndex % photos.length) + photos.length) % photos.length;
  renderLightboxFrame();
  document.getElementById("lightbox").classList.remove("hidden");
  document.getElementById("lightbox-close-btn").focus();
}

function closeLightbox() {
  const modal = document.getElementById("lightbox");
  if (!modal || modal.classList.contains("hidden")) return;
  modal.classList.add("hidden");
  document.getElementById("lightbox-img").removeAttribute("src");
  lightboxPhotos = [];
  if (lightboxReturnFocus && lightboxReturnFocus.isConnected) {
    lightboxReturnFocus.focus();
  }
  lightboxReturnFocus = null;
}

function stepLightbox(delta) {
  if (lightboxPhotos.length <= 1) return;
  lightboxIndex = (lightboxIndex + delta + lightboxPhotos.length) % lightboxPhotos.length;
  renderLightboxFrame();
}

function wireLightboxOnce() {
  if (lightboxWired) return;
  lightboxWired = true;

  document.querySelectorAll("[data-lightbox-close]").forEach((el) => {
    el.addEventListener("click", closeLightbox);
  });
  document.getElementById("lightbox-close-btn").addEventListener("click", closeLightbox);
  document.getElementById("lightbox-prev-btn").addEventListener("click", () => stepLightbox(-1));
  document.getElementById("lightbox-next-btn").addEventListener("click", () => stepLightbox(1));

  document.addEventListener("keydown", (event) => {
    const modal = document.getElementById("lightbox");
    if (!modal || modal.classList.contains("hidden")) return;
    if (event.key === "Escape") {
      event.preventDefault();
      closeLightbox();
    } else if (event.key === "ArrowLeft") {
      event.preventDefault();
      stepLightbox(-1);
    } else if (event.key === "ArrowRight") {
      event.preventDefault();
      stepLightbox(1);
    }
  });
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// ====================================================================
// GALLERY VIEW
// ====================================================================

async function initGallery() {
  const viewToken = ++activeViewToken;
  if (debounceTimer) clearTimeout(debounceTimer);
  closeLightbox();
  pendingBuild = false;
  projectManifest = null;
  currentParts = [];
  hasUnsavedCustomParams = false;
  lastBuildFromWasm = false;

  if (viewer) {
    viewer.dispose();
    viewer = null;
  }

  document.title = "Parametric CAD Showcase — build123d";
  workspaceView.classList.add("hidden");
  galleryView.classList.remove("hidden");
  wireLightboxOnce();

  if (galleryLoaded) return;

  const resp = await fetch("./manifest.json");
  if (!resp.ok) throw new Error(`Failed to fetch manifest.json (${resp.status})`);
  const manifest = await resp.json();
  if (viewToken !== activeViewToken) return;

  document.getElementById("repo-title").textContent = manifest.repo_title || "Parametric CAD Showcase";
  document.getElementById("repo-subtitle").textContent = manifest.repo_subtitle || "";

  const grid = document.getElementById("project-grid");
  grid.innerHTML = "";

  for (const proj of manifest.projects || []) {
    const projUrl = `?project=${encodeURIComponent(proj.slug)}`;
    const card = document.createElement("article");
    card.className = "project-card";

    const handleNav = (event) => {
      if (isModifiedClick(event)) return;
      event.preventDefault();
      navigateTo(proj.slug);
    };

    const bbox = proj.bbox || {};
    const dimTag = bbox.size_x
      ? `${bbox.size_x} × ${bbox.size_y} × ${bbox.size_z} mm`
      : "Parametric";

    const photos = Array.isArray(proj.photos) ? proj.photos : [];
    const frames = [
      { type: "cad", src: proj.thumb, alt: proj.title },
      ...photos.map((p, idx) => ({
        type: "photo",
        src: p.thumb_url || p.url,
        alt: p.caption || `${proj.title} printed photo ${idx + 1}`,
      })),
    ];

    const thumbBox = document.createElement("div");
    thumbBox.className = "card-thumb";

    const thumbLink = document.createElement("a");
    thumbLink.className = "card-thumb-link";
    thumbLink.href = projUrl;
    thumbLink.addEventListener("click", handleNav);

    const thumbImg = document.createElement("img");
    thumbImg.src = assetUrl(frames[0].src);
    thumbImg.alt = frames[0].alt;
    thumbImg.loading = "lazy";
    thumbLink.appendChild(thumbImg);
    thumbBox.appendChild(thumbLink);

    if (photos.length > 0) {
      let frameIdx = 0;

      const modePill = document.createElement("button");
      modePill.type = "button";
      modePill.className = "thumb-mode-pill";

      const expandBtn = document.createElement("button");
      expandBtn.type = "button";
      expandBtn.className = "thumb-expand-btn hidden";
      expandBtn.textContent = "⤢";
      expandBtn.setAttribute("aria-label", "Open full photo");
      expandBtn.title = "Open full photo";

      const prevBtn = document.createElement("button");
      prevBtn.type = "button";
      prevBtn.className = "thumb-nav thumb-nav-prev";
      prevBtn.innerHTML = "&lsaquo;";
      prevBtn.setAttribute("aria-label", "Previous preview image");

      const nextBtn = document.createElement("button");
      nextBtn.type = "button";
      nextBtn.className = "thumb-nav thumb-nav-next";
      nextBtn.innerHTML = "&rsaquo;";
      nextBtn.setAttribute("aria-label", "Next preview image");

      const dotsWrap = document.createElement("div");
      dotsWrap.className = "thumb-dots";
      const dots = frames.map((fr, idx) => {
        const dot = document.createElement("button");
        dot.type = "button";
        dot.className = "thumb-dot";
        dot.setAttribute("aria-label", idx === 0 ? "Show CAD render" : `Show printed photo ${idx}`);
        dot.addEventListener("click", (e) => {
          e.preventDefault();
          e.stopPropagation();
          setFrame(idx);
        });
        dotsWrap.appendChild(dot);
        return dot;
      });

      const setFrame = (nextIdx) => {
        frameIdx = (nextIdx + frames.length) % frames.length;
        const active = frames[frameIdx];
        thumbImg.src = assetUrl(active.src);
        thumbImg.alt = active.alt;

        const isPhoto = active.type === "photo";
        modePill.textContent = isPhoto
          ? "CAD"
          : `Photos (${photos.length})`;
        modePill.setAttribute(
          "aria-label",
          isPhoto ? "Switch to CAD render" : "Switch to printed photos"
        );
        expandBtn.classList.toggle("hidden", !isPhoto);
        dots.forEach((d, idx) => d.classList.toggle("active", idx === frameIdx));
      };

      modePill.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        setFrame(frameIdx === 0 ? 1 : 0);
      });

      expandBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (frameIdx > 0) openLightbox(photos, frameIdx - 1);
      });

      prevBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        setFrame(frameIdx - 1);
      });

      nextBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        setFrame(frameIdx + 1);
      });

      setFrame(0);
      thumbBox.append(modePill, expandBtn, prevBtn, nextBtn, dotsWrap);
    }

    const body = document.createElement("div");
    body.className = "card-body";
    body.innerHTML = `
      <h2><a class="card-title-link" href="${projUrl}">${escapeHtml(proj.title)}</a></h2>
      <p class="card-summary">${escapeHtml(proj.summary)}</p>
      <div class="card-meta">
        <span class="tag">${escapeHtml(dimTag)}</span>
        <span class="tag">${proj.volume_cm3} cm³</span>
        <span class="tag">${proj.param_count} sliders</span>
      </div>
      <a class="card-cta" href="${projUrl}">Open 3D Viewer &amp; Customizer &rarr;</a>
    `;
    body.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", handleNav);
    });
    body.addEventListener("click", (event) => {
      if (event.target.closest("a") || window.getSelection()?.toString()) return;
      handleNav(event);
    });

    card.append(thumbBox, body);
    grid.appendChild(card);
  }
  galleryLoaded = true;
}

// ====================================================================
// WORKSPACE VIEW (3D VIEWER + CUSTOMIZER)
// ====================================================================

function unpackBinaryMesh(arrayBuffer, partMetas) {
  let byteOffset = 0;
  return partMetas.map((meta) => {
    const posLen = meta.vertex_count * 3;
    const idxLen = meta.index_count;

    const positions = new Float32Array(arrayBuffer, byteOffset, posLen);
    byteOffset += posLen * 4;

    const indices = new Uint32Array(arrayBuffer, byteOffset, idxLen);
    byteOffset += idxLen * 4;

    return {
      name: meta.name,
      color: meta.color,
      opacity: meta.opacity,
      printable: meta.printable,
      assembly_offset: meta.assembly_offset,
      exploded_offset: meta.exploded_offset,
      positions,
      indices,
    };
  });
}

function setKernelStatus(stage, text, showOverlay = false) {
  const pill = document.getElementById("kernel-status");
  const statusText = document.getElementById("kernel-status-text");
  const overlay = document.getElementById("loading-overlay");
  const overlayText = document.getElementById("loading-overlay-text");

  pill.className = `status-pill status-${stage}`;
  statusText.textContent = text;
  overlayText.textContent = text;
  overlay.classList.toggle("hidden", !showOverlay);
}

function ensureWorker() {
  if (worker) return worker;

  worker = new Worker(new URL("./cad-worker.js", import.meta.url), { type: "module" });
  worker.onmessage = (event) => {
    const msg = event.data;
    if (msg.type === "status") {
      setKernelStatus(msg.stage, msg.detail, msg.stage === "busy");
      return;
    }

    if (msg.type === "inited") {
      kernelReady = true;
      kernelInitializing = false;
      document.getElementById("load-kernel-btn").textContent = "CAD Kernel Loaded";
      document.getElementById("load-kernel-btn").disabled = true;
      document.getElementById("wasm-hint").classList.add("hidden");
      resolvePending(msg.reqId, msg);
      if (pendingBuild) {
        pendingBuild = false;
        dispatchWorkerBuild();
      }
      return;
    }

    if (msg.type === "built") {
      buildInFlight = false;
      resolvePending(msg.reqId, msg);
      if (projectManifest && (!msg.slug || msg.slug === projectManifest.slug)) {
        lastBuildFromWasm = true;
        currentParts = msg.parts;
        viewer?.setParts(msg.parts, { resetCamera: false });
        renderMetrics(msg.metrics);
        renderExportButtons(msg.parts);
      }
      if (pendingBuild && projectManifest) {
        pendingBuild = false;
        dispatchWorkerBuild();
      }
      return;
    }

    if (msg.type === "exported") {
      resolvePending(msg.reqId, msg);
      return;
    }

    if (msg.type === "error") {
      kernelInitializing = false;
      buildInFlight = false;
      setKernelStatus("err", `Error: ${msg.message}`, false);
      rejectPending(msg.reqId, new Error(msg.message));
    }
  };

  worker.onerror = (err) => {
    console.error("CAD worker error:", err);
    kernelInitializing = false;
    buildInFlight = false;
    pendingBuild = false;
    kernelReady = false;
    const detail =
      err?.message ||
      (err?.filename ? `${err.filename}:${err.lineno || 0}` : "failed to load or parse cad-worker.js");
    if (worker) {
      worker.terminate();
      worker = null;
    }
    for (const [, entry] of pendingRequests.entries()) {
      entry.reject(new Error(`Worker crashed: ${detail}`));
    }
    pendingRequests.clear();
    document.getElementById("load-kernel-btn").textContent = "Enable Live Customizer (WASM)";
    document.getElementById("load-kernel-btn").disabled = false;
    setKernelStatus("err", `Worker crashed: ${detail}`, false);
  };

  worker.onmessageerror = (err) => {
    console.error("CAD worker message error:", err);
    kernelInitializing = false;
    buildInFlight = false;
    setKernelStatus("err", "Worker message serialization failed", false);
  };

  return worker;
}

function callWorker(payload) {
  const w = ensureWorker();
  const reqId = ++reqCounter;
  return new Promise((resolve, reject) => {
    pendingRequests.set(reqId, { resolve, reject });
    w.postMessage({ ...payload, reqId });
  });
}

function resolvePending(reqId, value) {
  const entry = pendingRequests.get(reqId);
  if (!entry) return;
  pendingRequests.delete(reqId);
  entry.resolve(value);
}

function rejectPending(reqId, err) {
  const entry = pendingRequests.get(reqId);
  if (!entry) return;
  pendingRequests.delete(reqId);
  entry.reject(err);
}

async function activateKernel() {
  if (kernelReady || kernelInitializing) return;
  kernelInitializing = true;
  const modelUrl = new URL(`./${projectManifest.model_url}`, window.location.href).href;
  await callWorker({
    type: "init",
    slug: projectManifest.slug,
    modelUrl,
    pyodideVersion,
    extraDeps: projectManifest.extra_deps || [],
  });
}

function scheduleWorkerBuild() {
  hasUnsavedCustomParams = true;
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    if (!kernelReady) {
      pendingBuild = true;
      activateKernel().catch(() => {});
      return;
    }
    if (buildInFlight) {
      pendingBuild = true;
      return;
    }
    dispatchWorkerBuild();
  }, 240);
}

function dispatchWorkerBuild() {
  if (!kernelReady || buildInFlight) {
    pendingBuild = true;
    return;
  }
  buildInFlight = true;
  const modelUrl = new URL(`./${projectManifest.model_url}`, window.location.href).href;
  callWorker({
    type: "build",
    slug: projectManifest.slug,
    modelUrl,
    pyodideVersion,
    extraDeps: projectManifest.extra_deps || [],
    params: currentParams,
    tolerance: 0.2,
  }).catch(() => {});
}

function renderControls(schema) {
  const container = document.getElementById("controls-container");
  container.innerHTML = "";

  const groups = new Map();
  for (const field of schema) {
    const grp = field.group || "Parameters";
    if (!groups.has(grp)) groups.set(grp, []);
    groups.get(grp).push(field);
  }

  for (const [groupName, fields] of groups.entries()) {
    const groupEl = document.createElement("div");
    groupEl.className = "control-group";

    const titleEl = document.createElement("div");
    titleEl.className = "group-title";
    titleEl.textContent = groupName;
    groupEl.appendChild(titleEl);

    for (const f of fields) {
      const rowEl = document.createElement("div");
      rowEl.className = "control-row";

      if (f.type === "boolean") {
        const label = document.createElement("label");
        label.className = "checkbox-row";
        label.innerHTML = `<span>${escapeHtml(f.label)}</span>`;
        const input = document.createElement("input");
        input.type = "checkbox";
        input.checked = Boolean(currentParams[f.key]);
        input.dataset.key = f.key;
        input.addEventListener("change", () => {
          currentParams[f.key] = input.checked;
          updateCliPreview();
          scheduleWorkerBuild();
        });
        label.appendChild(input);
        rowEl.appendChild(label);
      } else if (f.type === "select") {
        const label = document.createElement("div");
        label.className = "control-label";
        label.innerHTML = `<span>${escapeHtml(f.label)}</span>`;
        const select = document.createElement("select");
        select.dataset.key = f.key;
        for (const ch of f.choices || []) {
          const opt = document.createElement("option");
          opt.value = ch;
          opt.textContent = ch;
          if (currentParams[f.key] === ch) opt.selected = true;
          select.appendChild(opt);
        }
        select.addEventListener("change", () => {
          currentParams[f.key] = select.value;
          updateCliPreview();
          scheduleWorkerBuild();
        });
        rowEl.appendChild(label);
        rowEl.appendChild(select);
      } else {
        const unit = f.unit ? ` ${f.unit}` : "";
        const label = document.createElement("div");
        label.className = "control-label";
        label.innerHTML = `<span>${escapeHtml(f.label)}</span><span class="muted small">${escapeHtml(unit.trim())}</span>`;

        const line = document.createElement("div");
        line.className = "slider-line";

        const range = document.createElement("input");
        range.type = "range";
        range.min = f.min;
        range.max = f.max;
        range.step = f.step;
        range.value = currentParams[f.key];
        range.dataset.key = f.key;

        const num = document.createElement("input");
        num.type = "number";
        num.min = f.min;
        num.max = f.max;
        num.step = f.step;
        num.value = currentParams[f.key];
        num.dataset.key = f.key;

        const parseVal = (raw) =>
          f.type === "integer" ? parseInt(raw, 10) : parseFloat(raw);

        range.addEventListener("input", () => {
          const v = parseVal(range.value);
          if (Number.isNaN(v)) return;
          num.value = v;
          currentParams[f.key] = v;
          updateCliPreview();
          scheduleWorkerBuild();
        });

        num.addEventListener("change", () => {
          const v = parseVal(num.value);
          if (Number.isNaN(v)) return;
          range.value = v;
          currentParams[f.key] = v;
          updateCliPreview();
          scheduleWorkerBuild();
        });

        line.appendChild(range);
        line.appendChild(num);
        rowEl.appendChild(label);
        rowEl.appendChild(line);
      }

      groupEl.appendChild(rowEl);
    }

    container.appendChild(groupEl);
  }
}

function renderMetrics(metrics) {
  const container = document.getElementById("metrics-container");
  container.innerHTML = "";
  if (!metrics || metrics.length === 0) {
    container.innerHTML = `<div class="muted small">No printable metrics reported.</div>`;
    return;
  }

  for (const m of metrics) {
    const b = m.bbox || {};
    const volCm3 = (m.volume_mm3 || 0) / 1000.0;
    const estGrams = volCm3 * 1.24; // Typical PLA density reference

    const card = document.createElement("div");
    card.className = "metric-card";
    card.innerHTML = `
      <div class="metric-name">${escapeHtml(m.name)}</div>
      <div class="metric-grid">
        <div>Size X×Y×Z</div>
        <div>${b.size_x ?? "?"} × ${b.size_y ?? "?"} × ${b.size_z ?? "?"} mm</div>
        <div>Volume / ~PLA</div>
        <div>${volCm3.toFixed(1)} cm³ (~${estGrams.toFixed(0)} g)</div>
        <div>Print Bed (Z=0)</div>
        <div class="${m.bed_flat ? "badge-ok" : "badge-warn"}">${m.bed_flat ? "✔ Flat" : "⚠ Check Z_min"}</div>
        <div>Top Surface</div>
        <div class="${m.top_planar ? "badge-ok" : "badge-warn"}">${m.top_planar ? "✔ Planar" : "Tilted"}</div>
      </div>
    `;
    container.appendChild(card);
  }
}

function renderExportButtons(parts) {
  const container = document.getElementById("export-buttons");
  container.innerHTML = "";

  const printable = parts.filter((p) => p.printable);
  for (const p of printable) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn";
    btn.textContent = `Download ${p.name}.stl`;
    btn.addEventListener("click", async () => {
      if (kernelReady && lastBuildFromWasm) {
        const res = await callWorker({ type: "export_stl", partName: p.name });
        triggerDownload(new Blob([res.bytes], { type: res.mime }), res.filename);
      } else {
        const blob = buildBinaryStlFromMesh(p.positions, p.indices);
        triggerDownload(blob, `${p.name}.stl`);
      }
    });
    container.appendChild(btn);
  }

  const stepBtn = document.createElement("button");
  stepBtn.type = "button";
  stepBtn.className = "btn btn-primary";
  stepBtn.textContent = "Download Assembly (.step for Fusion)";
  stepBtn.addEventListener("click", async () => {
    stepBtn.disabled = true;
    try {
      const modelUrl = new URL(`./${projectManifest.model_url}`, window.location.href).href;
      const res = await callWorker({
        type: "export_step",
        slug: projectManifest.slug,
        modelUrl,
        pyodideVersion,
        extraDeps: projectManifest.extra_deps || [],
        params: currentParams,
      });
      triggerDownload(new Blob([res.bytes], { type: res.mime }), res.filename);
    } finally {
      stepBtn.disabled = false;
    }
  });
  container.appendChild(stepBtn);
}

function updateCliPreview() {
  const defaults = projectManifest.default_config || {};
  const flags = [];
  for (const f of projectManifest.schema || []) {
    if (f.cli && currentParams[f.key] !== defaults[f.key]) {
      flags.push(`${f.cli} ${currentParams[f.key]}`);
    }
  }
  const cmd = flags.length
    ? `cd projects/${projectManifest.slug} && ./generate.sh --fast ${flags.join(" ")}`
    : `cd projects/${projectManifest.slug} && ./generate.sh`;
  document.getElementById("cli-command").textContent = cmd;
}

function wireToolbarOnce() {
  if (toolbarWired) return;
  toolbarWired = true;

  document.getElementById("back-btn").addEventListener("click", (event) => {
    if (isModifiedClick(event)) return;
    event.preventDefault();
    navigateTo(null);
  });

  document.querySelectorAll("[data-cam]").forEach((btn) => {
    btn.addEventListener("click", () => viewer?.setCameraPreset(btn.dataset.cam));
  });

  const edgesBtn = document.getElementById("toggle-edges-btn");
  edgesBtn.addEventListener("click", () => {
    if (!viewer) return;
    const next = !viewer.showEdges;
    viewer.setShowEdges(next);
    edgesBtn.classList.toggle("active", next);
  });

  const gridBtn = document.getElementById("toggle-grid-btn");
  gridBtn.addEventListener("click", () => {
    if (!viewer) return;
    const next = !viewer.showGrid;
    viewer.setShowGrid(next);
    gridBtn.classList.toggle("active", next);
  });

  const refBtn = document.getElementById("toggle-ref-btn");
  refBtn.addEventListener("click", () => {
    if (!viewer) return;
    const next = !viewer.showReference;
    viewer.setShowReference(next);
    refBtn.classList.toggle("active", next);
  });

  const expBtn = document.getElementById("toggle-exploded-btn");
  expBtn.addEventListener("click", () => {
    if (!viewer) return;
    const next = !viewer.exploded;
    viewer.setExploded(next);
    expBtn.classList.toggle("active", next);
  });

  document.getElementById("load-kernel-btn").addEventListener("click", () => {
    activateKernel().catch(() => {});
  });

  document.getElementById("reset-params-btn").addEventListener("click", () => {
    if (!projectManifest) return;
    currentParams = { ...(projectManifest.default_config || {}) };
    renderControls(projectManifest.schema || []);
    updateCliPreview();
    if (kernelReady || hasUnsavedCustomParams) {
      scheduleWorkerBuild();
    }
  });

  document.getElementById("copy-cli-btn").addEventListener("click", async () => {
    const text = document.getElementById("cli-command").textContent;
    await navigator.clipboard?.writeText(text);
    const btn = document.getElementById("copy-cli-btn");
    btn.textContent = "Copied!";
    setTimeout(() => { btn.textContent = "Copy"; }, 1200);
  });
}

function renderPhotosPanel(photos) {
  const panel = document.getElementById("photos-panel");
  const countEl = document.getElementById("photos-count");
  const grid = document.getElementById("photos-grid");
  grid.innerHTML = "";

  if (!photos || photos.length === 0) {
    panel.classList.add("hidden");
    countEl.textContent = "";
    return;
  }

  panel.classList.remove("hidden");
  countEl.textContent = `(${photos.length})`;
  grid.classList.toggle("single", photos.length === 1);

  photos.forEach((photo, idx) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "photo-thumb-btn";
    btn.title = photo.caption || `Printed photo ${idx + 1}`;
    btn.setAttribute("aria-label", `Open photo ${idx + 1}: ${photo.caption || "Printed piece"}`);

    const img = document.createElement("img");
    img.src = assetUrl(photo.thumb_url || photo.url);
    img.alt = photo.caption || `Printed piece photo ${idx + 1}`;
    img.loading = "lazy";

    btn.appendChild(img);
    btn.addEventListener("click", () => openLightbox(photos, idx));
    grid.appendChild(btn);
  });
}

async function initWorkspace(slug) {
  const viewToken = ++activeViewToken;
  if (debounceTimer) clearTimeout(debounceTimer);
  closeLightbox();
  renderPhotosPanel([]);
  pendingBuild = false;
  hasUnsavedCustomParams = false;
  lastBuildFromWasm = false;

  if (viewer) {
    viewer.dispose();
    viewer = null;
  }

  galleryView.classList.add("hidden");
  workspaceView.classList.remove("hidden");
  wireToolbarOnce();
  wireLightboxOnce();

  // Reset per-view toggle button states to match fresh CadViewer defaults
  document.getElementById("toggle-edges-btn").classList.add("active");
  document.getElementById("toggle-grid-btn").classList.add("active");
  document.getElementById("toggle-ref-btn").classList.add("active");
  document.getElementById("toggle-exploded-btn").classList.remove("active");

  if (kernelReady) {
    setKernelStatus("ready", "Live CAD Ready (Cached in RAM)", false);
    document.getElementById("load-kernel-btn").textContent = "CAD Kernel Loaded";
    document.getElementById("load-kernel-btn").disabled = true;
    document.getElementById("wasm-hint").classList.add("hidden");
  } else if (kernelInitializing) {
    setKernelStatus("busy", "Loading Live CAD Kernel…", false);
    document.getElementById("load-kernel-btn").textContent = "Loading CAD Kernel…";
    document.getElementById("load-kernel-btn").disabled = true;
    document.getElementById("wasm-hint").classList.remove("hidden");
  } else {
    setKernelStatus("idle", "Static Preview", false);
    document.getElementById("load-kernel-btn").textContent = "Enable Live Customizer (WASM)";
    document.getElementById("load-kernel-btn").disabled = false;
    document.getElementById("wasm-hint").classList.remove("hidden");
  }

  const manifestResp = await fetch(`./projects/${encodeURIComponent(slug)}/manifest.json`);
  if (!manifestResp.ok) throw new Error(`Project '${slug}' not found (${manifestResp.status})`);
  const manifest = await manifestResp.json();
  if (viewToken !== activeViewToken) return;
  projectManifest = manifest;

  document.title = `${projectManifest.title} — build123d`;
  document.getElementById("project-title").textContent = projectManifest.title;
  document.getElementById("project-summary").textContent = projectManifest.summary;

  currentParams = { ...(projectManifest.default_config || {}) };

  const meshResp = await fetch(`./${projectManifest.mesh_url}`);
  if (!meshResp.ok) throw new Error(`Failed to load default mesh (${meshResp.status})`);
  const meshBuf = await meshResp.arrayBuffer();
  if (viewToken !== activeViewToken) return;
  currentParts = unpackBinaryMesh(meshBuf, projectManifest.parts || []);

  viewer = new CadViewer(document.getElementById("viewport-canvas-wrap"));
  viewer.setParts(currentParts, { resetCamera: true });

  // Show contextual viewport toggles only when relevant
  const hasReference = currentParts.some((p) => !p.printable);
  const hasExploded = currentParts.some((p) => {
    const a = p.assembly_offset || [0, 0, 0];
    const e = p.exploded_offset || a;
    return Math.hypot(a[0] - e[0], a[1] - e[1], a[2] - e[2]) > 0.1;
  });
  document.getElementById("toggle-ref-btn").classList.toggle("hidden", !hasReference);
  document.getElementById("toggle-exploded-btn").classList.toggle("hidden", !hasExploded);

  renderPhotosPanel(projectManifest.photos || []);
  renderControls(projectManifest.schema || []);
  renderMetrics(projectManifest.metrics || []);
  renderExportButtons(currentParts);
  updateCliPreview();
}

window.addEventListener("popstate", () => {
  routeToCurrentLocation().catch(renderFatalError);
});

// Entrypoint
routeToCurrentLocation().catch(renderFatalError);
