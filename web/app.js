import { CadViewer, buildBinaryStlFromMesh } from "./viewer.js";

const searchParams = new URLSearchParams(window.location.search);
const projectSlug = searchParams.get("project");
const pyodideVersion = searchParams.get("pyodide") || "v314.0.7";

const galleryView = document.getElementById("gallery-view");
const workspaceView = document.getElementById("workspace-view");

let viewer = null;
let projectManifest = null;
let currentParams = {};
let currentParts = [];
let hasUnsavedCustomParams = false;
let lastBuildFromWasm = false;

let worker = null;
let kernelReady = false;
let kernelInitializing = false;
let buildInFlight = false;
let pendingBuild = false;
let debounceTimer = null;
let reqCounter = 0;
const pendingRequests = new Map();

function escapeHtml(str) {
  return String(str)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
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
  galleryView.classList.remove("hidden");
  const resp = await fetch("./manifest.json");
  if (!resp.ok) throw new Error(`Failed to fetch manifest.json (${resp.status})`);
  const manifest = await resp.json();

  document.getElementById("repo-title").textContent = manifest.repo_title || "Parametric CAD Showcase";
  document.getElementById("repo-subtitle").textContent = manifest.repo_subtitle || "";

  const grid = document.getElementById("project-grid");
  grid.innerHTML = "";

  for (const proj of manifest.projects || []) {
    const card = document.createElement("a");
    card.className = "project-card";
    card.href = `?project=${encodeURIComponent(proj.slug)}`;

    const bbox = proj.bbox || {};
    const dimTag = bbox.size_x
      ? `${bbox.size_x} × ${bbox.size_y} × ${bbox.size_z} mm`
      : "Parametric";

    const thumbUrl = proj.thumb;
    card.innerHTML = `
      <div class="card-thumb">
        <img src="./${escapeHtml(thumbUrl)}" alt="${escapeHtml(proj.title)}" loading="lazy" />
      </div>
      <div class="card-body">
        <h2>${escapeHtml(proj.title)}</h2>
        <p class="card-summary">${escapeHtml(proj.summary)}</p>
        <div class="card-meta">
          <span class="tag">${escapeHtml(dimTag)}</span>
          <span class="tag">${proj.volume_cm3} cm³</span>
          <span class="tag">${proj.param_count} sliders</span>
        </div>
        <div class="card-cta">Open 3D Viewer &amp; Customizer &rarr;</div>
      </div>
    `;
    grid.appendChild(card);
  }
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

  worker = new Worker("./cad-worker.js", { type: "module" });
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
      lastBuildFromWasm = true;
      currentParts = msg.parts;
      viewer.setParts(msg.parts, { resetCamera: false });
      renderMetrics(msg.metrics);
      renderExportButtons(msg.parts);
      resolvePending(msg.reqId, msg);
      if (pendingBuild) {
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
    kernelInitializing = false;
    buildInFlight = false;
    setKernelStatus("err", `Worker crashed: ${err.message}`, false);
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

async function initWorkspace(slug) {
  workspaceView.classList.remove("hidden");

  const manifestResp = await fetch(`./projects/${encodeURIComponent(slug)}/manifest.json`);
  if (!manifestResp.ok) throw new Error(`Project '${slug}' not found (${manifestResp.status})`);
  projectManifest = await manifestResp.json();

  document.title = `${projectManifest.title} — build123d`;
  document.getElementById("project-title").textContent = projectManifest.title;
  document.getElementById("project-summary").textContent = projectManifest.summary;

  currentParams = { ...(projectManifest.default_config || {}) };

  const meshResp = await fetch(`./${projectManifest.mesh_url}`);
  if (!meshResp.ok) throw new Error(`Failed to load default mesh (${meshResp.status})`);
  const meshBuf = await meshResp.arrayBuffer();
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

  renderControls(projectManifest.schema || []);
  renderMetrics(projectManifest.metrics || []);
  renderExportButtons(currentParts);
  updateCliPreview();

  // Wire toolbar controls
  document.querySelectorAll("[data-cam]").forEach((btn) => {
    btn.addEventListener("click", () => viewer.setCameraPreset(btn.dataset.cam));
  });

  const edgesBtn = document.getElementById("toggle-edges-btn");
  edgesBtn.addEventListener("click", () => {
    const next = !viewer.showEdges;
    viewer.setShowEdges(next);
    edgesBtn.classList.toggle("active", next);
  });

  const gridBtn = document.getElementById("toggle-grid-btn");
  gridBtn.addEventListener("click", () => {
    const next = !viewer.showGrid;
    viewer.setShowGrid(next);
    gridBtn.classList.toggle("active", next);
  });

  const refBtn = document.getElementById("toggle-ref-btn");
  refBtn.addEventListener("click", () => {
    const next = !viewer.showReference;
    viewer.setShowReference(next);
    refBtn.classList.toggle("active", next);
  });

  const expBtn = document.getElementById("toggle-exploded-btn");
  expBtn.addEventListener("click", () => {
    const next = !viewer.exploded;
    viewer.setExploded(next);
    expBtn.classList.toggle("active", next);
  });

  document.getElementById("load-kernel-btn").addEventListener("click", () => {
    activateKernel().catch(() => {});
  });

  document.getElementById("reset-params-btn").addEventListener("click", () => {
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

// Entrypoint
(async () => {
  try {
    if (projectSlug) {
      await initWorkspace(projectSlug);
    } else {
      await initGallery();
    }
  } catch (err) {
    console.error(err);
    document.body.innerHTML = `<div style="padding:32px;font-family:sans-serif;color:#f87171;">
      <h2>Failed to load CAD preview</h2>
      <pre>${escapeHtml(err?.stack || err?.message || String(err))}</pre>
      <p><a href="./" style="color:#38bdf8;">Back to project gallery</a></p>
    </div>`;
  }
})();
