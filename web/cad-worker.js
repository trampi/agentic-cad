let pyodide = null;
let initialized = false;
let currentProjectSlug = null;

const WASM_CACHE_PREFIX = "agentic-cad-wasm-";
const WASM_CACHE_SCHEMA = "v2";
const IMMUTABLE_CACHE_PREFIXES = [
  "https://cdn.jsdelivr.net/pyodide/",
  "https://files.pythonhosted.org/",
];
const INDEX_CACHE_PREFIXES = [
  "https://pypi.org/pypi/",
  "https://pypi.org/simple/",
  "https://yeicor.github.io/OCP.wasm/",
];

let activeCacheName = `${WASM_CACHE_PREFIX}default-${WASM_CACHE_SCHEMA}`;
let wasmCachePromise = null;
let lastEvictedFor = null;
const cacheStats = {
  available: typeof self.caches !== "undefined",
  hits: 0,
  misses: 0,
  cachedBytes: 0,
  netBytes: 0,
};

function resetCacheStats() {
  cacheStats.hits = 0;
  cacheStats.misses = 0;
  cacheStats.cachedBytes = 0;
  cacheStats.netBytes = 0;
}

function setActiveCacheVersion(pyodideVersion) {
  const nextName = `${WASM_CACHE_PREFIX}${pyodideVersion}-${WASM_CACHE_SCHEMA}`;
  if (nextName !== activeCacheName) {
    activeCacheName = nextName;
    wasmCachePromise = null;
  }
}

async function evictStaleCacheBuckets(keepName, force = false) {
  if (typeof self.caches === "undefined" || (!force && lastEvictedFor === keepName)) return;
  lastEvictedFor = keepName;
  try {
    const names = await self.caches.keys();
    await Promise.all(
      names
        .filter((name) => name.startsWith(WASM_CACHE_PREFIX) && name !== keepName)
        .map((name) => self.caches.delete(name))
    );
  } catch (_) {
    // Ignore storage enumeration failures
  }
}

function openWasmCache() {
  if (typeof self.caches === "undefined") return Promise.resolve(null);
  if (!wasmCachePromise) {
    wasmCachePromise = (async () => {
      try {
        const cache = await self.caches.open(activeCacheName);
        await evictStaleCacheBuckets(activeCacheName);
        return cache;
      } catch (_) {
        return null;
      }
    })();
  }
  return wasmCachePromise;
}

function resolveRequestUrl(resource) {
  if (typeof resource === "string") return resource;
  if (typeof URL !== "undefined" && resource instanceof URL) return resource.href;
  return resource?.url || resource?.href || "";
}

function wheelPackageStem(urlStr) {
  try {
    const pathname = new URL(urlStr).pathname;
    const fname = pathname.slice(pathname.lastIndexOf("/") + 1);
    const m = /^([A-Za-z0-9_.]+)-\d/.exec(fname);
    return m ? `${m[1]}-` : null;
  } catch (_) {
    return null;
  }
}

async function pruneOlderWheelVersions(cache, currentWheelUrl) {
  const stem = wheelPackageStem(currentWheelUrl);
  if (!stem) return;
  try {
    const keys = await cache.keys();
    await Promise.all(
      keys
        .filter((req) => {
          if (req.url === currentWheelUrl || !req.url.endsWith(".whl")) return false;
          const fname = req.url.slice(req.url.lastIndexOf("/") + 1);
          return fname.startsWith(stem);
        })
        .map((req) => cache.delete(req))
    );
  } catch (_) {
    // Non-fatal
  }
}

async function putCacheWithQuotaRetry(cache, cacheUrl, response) {
  try {
    await cache.put(cacheUrl, response.clone());
    if (cacheUrl.endsWith(".whl")) {
      await pruneOlderWheelVersions(cache, cacheUrl);
    }
    return true;
  } catch (err) {
    if (err?.name === "QuotaExceededError") {
      try {
        await evictStaleCacheBuckets(activeCacheName, true);
        await pruneOlderWheelVersions(cache, cacheUrl);
        await cache.put(cacheUrl, response.clone());
        return true;
      } catch (_) {
        // Still over quota
      }
    }
    return false;
  }
}

function installGlobalFetchCache() {
  if (typeof self.fetch !== "function" || typeof self.caches === "undefined") return;
  const rawFetch = self.fetch.bind(self);

  self.fetch = async function cachedFetch(resource, init) {
    const reqUrl = resolveRequestUrl(resource);
    const method = (init?.method || (typeof resource !== "string" && !(resource instanceof URL) && resource?.method) || "GET").toUpperCase();
    const hasRange = Boolean(
      (init?.headers && new Headers(init.headers).has("Range")) ||
      (typeof resource !== "string" && !(resource instanceof URL) && resource?.headers?.has("Range"))
    );

    if (!reqUrl || method !== "GET" || hasRange) {
      return rawFetch(resource, init);
    }

    const isImmutable = IMMUTABLE_CACHE_PREFIXES.some((p) => reqUrl.startsWith(p));
    const isIndex = !isImmutable && INDEX_CACHE_PREFIXES.some((p) => reqUrl.startsWith(p));
    if (!isImmutable && !isIndex) {
      return rawFetch(resource, init);
    }

    const cache = await openWasmCache();
    if (!cache) {
      return rawFetch(resource, init);
    }

    if (isIndex) {
      // Network-first via browser HTTP cache so new library releases are picked up immediately;
      // fall back to CacheStorage only if offline.
      try {
        const fresh = await rawFetch(resource, init);
        if (fresh.status === 200 && fresh.type !== "opaque") {
          await putCacheWithQuotaRetry(cache, reqUrl, fresh);
        }
        return fresh;
      } catch (err) {
        try {
          const fallback = await cache.match(reqUrl, { ignoreVary: true });
          if (fallback) return fallback;
        } catch (_) {
          // Ignore cache fallback read error
        }
        throw err;
      }
    }

    try {
      const cached = await cache.match(reqUrl, { ignoreVary: true });
      if (cached) {
        cacheStats.hits++;
        cacheStats.cachedBytes += Number(cached.headers.get("content-length") || 0);
        return cached;
      }
    } catch (_) {
      // Fall through to network if CacheStorage read fails
    }

    const response = await rawFetch(resource, init);
    cacheStats.misses++;
    cacheStats.netBytes += Number(response.headers.get("content-length") || 0);
    if (response.status === 200 && response.type !== "opaque") {
      await putCacheWithQuotaRetry(cache, reqUrl, response);
    }
    return response;
  };
}

installGlobalFetchCache();

async function hasCachedOcpWheel() {
  const cache = await openWasmCache();
  if (!cache) return false;
  try {
    const keys = await cache.keys();
    return keys.some((req) => req.url.includes("cadquery_ocp_novtk") && req.url.endsWith(".whl"));
  } catch (_) {
    return false;
  }
}

function formatCacheReadyDetail() {
  if (!cacheStats.available) {
    return "Live CAD Kernel Ready (Cache API disabled on insecure URL)";
  }
  const cachedMb = (cacheStats.cachedBytes / (1024 * 1024)).toFixed(1);
  const netMb = (cacheStats.netBytes / (1024 * 1024)).toFixed(1);
  if (cacheStats.hits > 0 && cacheStats.misses === 0) {
    return `Live CAD Kernel Ready (from Cache · ${cachedMb} MB)`;
  }
  if (cacheStats.hits > 0) {
    return `Live CAD Kernel Ready (${cacheStats.hits} cached · ${netMb} MB net)`;
  }
  return `Live CAD Kernel Ready (cached ${netMb} MB for reloads)`;
}

function emitStatus(stage, detail) {
  self.postMessage({ type: "status", stage, detail });
}

const BOOTSTRAP_PYTHON = `
import array
import copy
import importlib
import importlib.abc
import importlib.util
import json
import sys
import tempfile
import types
from dataclasses import fields, is_dataclass
from pathlib import Path

_LAST_PARTS = []
_LAST_CFG = None

DEFAULT_STUB_ROOTS = {
    "scipy", "sklearn", "IPython", "lib3mf", "PIL", "requests",
    "bd_materials", "threejs_materials", "ezdxf", "fontTools",
    "svgpathtools", "ocpsvg", "ocp_gordon", "trianglesolver",
    "webcolors", "sympy",
}

class _StubType(type):
    def __getattr__(cls, k):
        return _StubType(f"{cls.__name__}.{k}", (), {})
    def __call__(cls, *a, **kw):
        return _StubObj(cls.__name__)
    def __or__(cls, other):
        return cls
    def __ror__(cls, other):
        return cls

class _StubObj(metaclass=_StubType):
    def __init__(self, name=""):
        self._name = name
    def __getattr__(self, k):
        return _StubObj(f"{self._name}.{k}")
    def __call__(self, *a, **kw):
        return _StubObj(self._name)
    def __iter__(self):
        return iter(())
    def __bool__(self):
        return False
    def __or__(self, other):
        return self
    def __ror__(self, other):
        return self

class _StubModule(types.ModuleType):
    __path__ = []
    def __getattr__(self, k):
        if k in ("__spec__", "__loader__", "__file__", "__all__"):
            raise AttributeError(k)
        return _StubType(f"{self.__name__}.{k}", (), {"__getattr__": lambda s, x: _StubObj(x)})

class _StubFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, roots):
        self.roots = set(roots)
    def find_spec(self, fullname, path, target=None):
        if fullname.split(".")[0] in self.roots:
            return importlib.util.spec_from_loader(fullname, self, is_package=True)
        return None
    def create_module(self, spec):
        m = _StubModule(spec.name)
        m.__path__ = []
        return m
    def exec_module(self, module):
        pass

def install_stubs(extra_deps):
    roots = DEFAULT_STUB_ROOTS - set(extra_deps or [])
    sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, _StubFinder)]
    sys.meta_path.insert(0, _StubFinder(roots))

def load_project_source(source_text):
    proj_dir = Path(tempfile.gettempdir()) / "cad_project"
    proj_dir.mkdir(parents=True, exist_ok=True)
    (proj_dir / "model.py").write_text(source_text, encoding="utf-8")
    if str(proj_dir) not in sys.path:
        sys.path.insert(0, str(proj_dir))
    if "model" in sys.modules:
        del sys.modules["model"]
    import model

def _coerce_cfg(cfg_cls, params):
    if not is_dataclass(cfg_cls):
        return cfg_cls()
    kwargs = {}
    for f in fields(cfg_cls):
        if f.name not in params:
            continue
        val = params[f.name]
        if isinstance(f.default, bool):
            kwargs[f.name] = bool(val)
        elif isinstance(f.default, int):
            kwargs[f.name] = int(round(float(val)))
        elif isinstance(f.default, float):
            kwargs[f.name] = float(val)
        else:
            kwargs[f.name] = val
    return cfg_cls(**kwargs)

def build_model_payload(params_json, tolerance=0.2):
    global _LAST_PARTS, _LAST_CFG
    import model
    params = json.loads(params_json)
    cfg = _coerce_cfg(model.Config, params)
    _LAST_CFG = cfg

    if hasattr(model, "build_web_parts"):
        parts = model.build_web_parts(cfg)
    else:
        parts = []
        for attr in dir(model):
            if attr.startswith("create_") and callable(getattr(model, attr)):
                try:
                    shape = getattr(model, attr)(cfg)
                except TypeError:
                    continue
                if hasattr(shape, "tessellate"):
                    parts.append({
                        "name": attr.removeprefix("create_"),
                        "shape": shape,
                        "color": (0.25, 0.45, 0.75),
                        "opacity": 1.0,
                        "printable": True,
                        "assembly_offset": (0.0, 0.0, 0.0),
                        "exploded_offset": (0.0, 0.0, 0.0),
                    })

    _LAST_PARTS = parts
    part_outputs = []
    metrics = []

    for item in parts:
        shape = item["shape"]
        verts, tris = shape.tessellate(float(tolerance))
        pos_arr = array.array("f", [c for v in verts for c in (float(v.X), float(v.Y), float(v.Z))])
        idx_arr = array.array("I", [i for t in tris for i in (int(t[0]), int(t[1]), int(t[2]))])

        pos_bytes = bytes(memoryview(pos_arr).cast("B"))
        idx_bytes = bytes(memoryview(idx_arr).cast("B"))

        part_outputs.append({
            "name": item["name"],
            "color": [float(c) for c in item.get("color", (0.25, 0.45, 0.75))],
            "opacity": float(item.get("opacity", 1.0)),
            "printable": bool(item.get("printable", True)),
            "assembly_offset": [float(x) for x in item.get("assembly_offset", (0.0, 0.0, 0.0))],
            "exploded_offset": [float(x) for x in item.get("exploded_offset", item.get("assembly_offset", (0.0, 0.0, 0.0)))],
            "pos_bytes": pos_bytes,
            "idx_bytes": idx_bytes,
        })

        if item.get("printable", True) and hasattr(model, "analyze_part_geometry"):
            metrics.append(model.analyze_part_geometry(item["name"], shape))

    return {
        "parts": part_outputs,
        "metrics_json": json.dumps(metrics),
    }

def export_part_stl_bytes(part_name):
    import build123d
    target = next((p for p in _LAST_PARTS if p["name"] == part_name), None)
    if target is None:
        raise KeyError(f"Part not found: {part_name}")
    with tempfile.NamedTemporaryFile(suffix=".stl") as f:
        build123d.export_stl(target["shape"], f.name)
        return Path(f.name).read_bytes()

def export_assembly_step_bytes():
    import build123d
    solids = []
    for p in _LAST_PARTS:
        off = p.get("assembly_offset", (0.0, 0.0, 0.0))
        s = copy.copy(p["shape"])
        if any(abs(v) > 1e-6 for v in off):
            s = s.move(build123d.Location(tuple(off)))
        s.label = p["name"]
        solids.append(s)
    compound = solids[0] if len(solids) == 1 else build123d.Compound(solids, label="WebAssembly")
    with tempfile.NamedTemporaryFile(suffix=".step") as f:
        build123d.export_step(compound, f.name)
        return Path(f.name).read_bytes()
`;

async function ensureKernel(pyodideVersion = "v314.0.7", extraDeps = []) {
  if (initialized) return;

  setActiveCacheVersion(pyodideVersion);
  resetCacheStats();
  await openWasmCache();

  const cachedOcp = await hasCachedOcpWheel();
  const baseUrl = `https://cdn.jsdelivr.net/pyodide/${pyodideVersion}/full/`;
  emitStatus(
    "busy",
    cachedOcp
      ? `Loading cached Pyodide (${pyodideVersion})…`
      : `Loading Pyodide (${pyodideVersion})…`
  );

  const mod = await import(`${baseUrl}pyodide.mjs`);
  pyodide = await mod.loadPyodide({ indexURL: baseUrl });

  emitStatus("busy", "Loading micropip & numpy…");
  await pyodide.loadPackage(["micropip", "numpy"]);

  pyodide.runPython(BOOTSTRAP_PYTHON);
  pyodide.globals.get("install_stubs")(extraDeps);

  emitStatus(
    "busy",
    cachedOcp
      ? "Loading cached OCP.wasm & build123d…"
      : "Downloading OCP.wasm & build123d (~25 MB, cached once)…"
  );
  const purePkgs = ["build123d", "anytree>=2.8.0,<3", ...extraDeps];
  await pyodide.runPythonAsync(`
    import importlib
    import sys
    import micropip

    async def _install_ocp_wasm():
        attempts = []
        try:
            await micropip.install("cadquery-ocp-novtk-OCP.wasm", deps=False)
            return
        except Exception as exc:
            attempts.append(f"PyPI cadquery-ocp-novtk-OCP.wasm: {exc}")

        micropip.set_index_urls([
            "https://yeicor.github.io/OCP.wasm/",
            "https://pypi.org/simple/",
        ])
        for candidate in ("cadquery-ocp-novtk-OCP.wasm", "cadquery-ocp-novtk"):
            try:
                await micropip.install(candidate, deps=False)
                return
            except Exception as exc:
                attempts.append(f"OCP.wasm index {candidate}: {exc}")

        try:
            from packaging.tags import sys_tags
            tags = ", ".join(str(t) for t in list(sys_tags())[:6])
        except Exception:
            tags = "unknown"
        raise RuntimeError(
            "Unable to install a WebAssembly OCP wheel for this Pyodide runtime "
            f"[{tags}]. Attempts: {' | '.join(attempts)}"
        )

    await _install_ocp_wasm()
    await micropip.install(${JSON.stringify(purePkgs)}, deps=False)

    # Pyodide may pre-bundle an older typing_extensions without sentinel (added in 4.16.0)
    _need_te = False
    try:
        import typing_extensions as _te
        _need_te = not hasattr(_te, "sentinel")
    except ImportError:
        _need_te = True

    if _need_te:
        try:
            await micropip.install("typing_extensions>=4.16.0,<5", deps=False, reinstall=True)
        except TypeError:
            await micropip.install("typing_extensions>=4.16.0,<5", deps=False)
        sys.modules.pop("typing_extensions", None)

    importlib.invalidate_caches()
    import typing_extensions as _te
    if not hasattr(_te, "sentinel"):
        raise RuntimeError(f"typing_extensions>=4.16.0 required (loaded from {getattr(_te, '__file__', '?')})")

    # Verify import and auto-install any missing tiny pure-python package if needed
    for _ in range(8):
        try:
            import build123d
            break
        except ModuleNotFoundError as exc:
            missing = (exc.name or "").split(".")[0]
            if not missing:
                raise
            await micropip.install(missing, deps=False)
            importlib.invalidate_caches()
  `);

  initialized = true;
}

async function loadProject(slug, modelUrl, pyodideVersion, extraDeps) {
  await ensureKernel(pyodideVersion, extraDeps);
  if (currentProjectSlug === slug) return;

  emitStatus("busy", `Loading ${slug}/model.py…`);
  const resp = await fetch(modelUrl);
  if (!resp.ok) throw new Error(`Failed to fetch ${modelUrl} (${resp.status})`);
  const sourceText = await resp.text();
  const loadFn = pyodide.globals.get("load_project_source");
  loadFn(sourceText);
  loadFn.destroy();
  currentProjectSlug = slug;
}

function takeJsValue(pyVal) {
  if (pyVal && typeof pyVal.toJs === "function") {
    const jsVal = pyVal.toJs({ create_pyproxies: false });
    pyVal.destroy();
    return jsVal;
  }
  return pyVal;
}

function takeAlignedBytes(pyVal) {
  const raw = takeJsValue(pyVal);
  // Always copy into a standalone Uint8Array so byteOffset is 0 (4-byte aligned),
  // Uint8ClampedArray becomes Uint8Array, and transferring its buffer never detaches WASM memory.
  return new Uint8Array(raw);
}

self.onmessage = async (event) => {
  const msg = event.data;
  try {
    if (msg.type === "init") {
      await loadProject(msg.slug, msg.modelUrl, msg.pyodideVersion, msg.extraDeps || []);
      emitStatus("ready", formatCacheReadyDetail());
      self.postMessage({ type: "inited", reqId: msg.reqId, slug: msg.slug });
      return;
    }

    if (msg.type === "build") {
      await loadProject(msg.slug, msg.modelUrl, msg.pyodideVersion, msg.extraDeps || []);
      emitStatus("busy", "Rebuilding B-Rep geometry…");

      const t0 = performance.now();
      const buildFn = pyodide.globals.get("build_model_payload");
      const pyResult = buildFn(JSON.stringify(msg.params), msg.tolerance ?? 0.2);
      buildFn.destroy();

      const pyParts = pyResult.get("parts");
      const metricsJson = takeJsValue(pyResult.get("metrics_json"));

      const jsParts = [];
      const transferables = [];

      const count = pyParts.length;
      for (let i = 0; i < count; i++) {
        const item = pyParts.get(i);
        const posU8 = takeAlignedBytes(item.get("pos_bytes"));
        const idxU8 = takeAlignedBytes(item.get("idx_bytes"));

        const positions = new Float32Array(posU8.buffer, 0, posU8.byteLength / 4);
        const indices = new Uint32Array(idxU8.buffer, 0, idxU8.byteLength / 4);

        jsParts.push({
          name: takeJsValue(item.get("name")),
          color: takeJsValue(item.get("color")),
          opacity: takeJsValue(item.get("opacity")),
          printable: takeJsValue(item.get("printable")),
          assembly_offset: takeJsValue(item.get("assembly_offset")),
          exploded_offset: takeJsValue(item.get("exploded_offset")),
          positions,
          indices,
        });

        item.destroy();

        transferables.push(positions.buffer, indices.buffer);
      }

      pyParts.destroy();
      pyResult.destroy();

      const elapsedMs = Math.round(performance.now() - t0);
      emitStatus("ready", `Live CAD Ready (${elapsedMs} ms)`);

      self.postMessage(
        {
          type: "built",
          reqId: msg.reqId,
          slug: msg.slug,
          parts: jsParts,
          metrics: JSON.parse(metricsJson),
          elapsedMs,
        },
        transferables
      );
      return;
    }

    if (msg.type === "export_stl") {
      emitStatus("busy", `Exporting ${msg.partName}.stl…`);
      const fn = pyodide.globals.get("export_part_stl_bytes");
      const u8 = takeAlignedBytes(fn(msg.partName));
      fn.destroy();
      emitStatus("ready", "Live CAD Ready");
      self.postMessage(
        { type: "exported", reqId: msg.reqId, filename: `${msg.partName}.stl`, bytes: u8, mime: "model/stl" },
        [u8.buffer]
      );
      return;
    }

    if (msg.type === "export_step") {
      await loadProject(msg.slug, msg.modelUrl, msg.pyodideVersion, msg.extraDeps || []);
      emitStatus("busy", "Exporting exact B-Rep STEP…");
      const buildFn = pyodide.globals.get("build_model_payload");
      const pyRes = buildFn(JSON.stringify(msg.params), 0.5);
      buildFn.destroy();
      pyRes.destroy();

      const fn = pyodide.globals.get("export_assembly_step_bytes");
      const u8 = takeAlignedBytes(fn());
      fn.destroy();
      emitStatus("ready", "Live CAD Ready");
      self.postMessage(
        { type: "exported", reqId: msg.reqId, filename: `${msg.slug}.step`, bytes: u8, mime: "application/step" },
        [u8.buffer]
      );
    }
  } catch (err) {
    emitStatus("err", "Kernel Error");
    self.postMessage({
      type: "error",
      reqId: msg.reqId,
      message: err?.message || String(err),
    });
  }
};
