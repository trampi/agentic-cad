import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

export class CadViewer {
  constructor(container) {
    this.container = container;
    this.showEdges = true;
    this.showGrid = true;
    this.showReference = true;
    this.exploded = false;
    this.partRecords = [];
    this.hasFramedOnce = false;
    this._disposed = false;
    this._rafId = 0;

    this.scene = new THREE.Scene();

    const w = Math.max(1, container.clientWidth);
    const h = Math.max(1, container.clientHeight);
    this.camera = new THREE.PerspectiveCamera(42, w / h, 0.5, 5000);
    this.camera.up.set(0, 0, 1);
    this.camera.position.set(180, -200, 160);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(w, h);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.dampingFactor = 0.08;

    this._setupLights();
    this._setupGrid();

    this.modelGroup = new THREE.Group();
    this.scene.add(this.modelGroup);

    this._resizeObserver = new ResizeObserver(() => this._onResize());
    this._resizeObserver.observe(container);
    this._animate();
  }

  _setupLights() {
    this.scene.add(new THREE.HemisphereLight(0xe2e8f0, 0x1e293b, 0.95));

    const key = new THREE.DirectionalLight(0xffffff, 1.15);
    key.position.set(180, -220, 320);
    this.scene.add(key);

    const fill = new THREE.DirectionalLight(0x93c5fd, 0.45);
    fill.position.set(-220, 160, 140);
    this.scene.add(fill);

    const rim = new THREE.DirectionalLight(0xffffff, 0.35);
    rim.position.set(0, 260, -90);
    this.scene.add(rim);
  }

  _setupGrid() {
    this.gridGroup = new THREE.Group();

    const grid = new THREE.GridHelper(320, 32, 0x334155, 0x1e293b);
    grid.rotation.x = Math.PI / 2;
    grid.position.z = -0.05;
    this.gridGroup.add(grid);

    // Subtle 220 x 220 mm print-bed boundary reference centered around XY origin
    const bedHalf = 110;
    const bedPts = [
      new THREE.Vector3(-bedHalf, -bedHalf, 0),
      new THREE.Vector3(bedHalf, -bedHalf, 0),
      new THREE.Vector3(bedHalf, bedHalf, 0),
      new THREE.Vector3(-bedHalf, bedHalf, 0),
    ];
    const bedGeo = new THREE.BufferGeometry().setFromPoints(bedPts);
    const bedMat = new THREE.LineBasicMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.35,
    });
    this.gridGroup.add(new THREE.LineLoop(bedGeo, bedMat));

    const axes = new THREE.AxesHelper(35);
    this.gridGroup.add(axes);

    this.scene.add(this.gridGroup);
  }

  _onResize() {
    const w = Math.max(1, this.container.clientWidth);
    const h = Math.max(1, this.container.clientHeight);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  _animate() {
    if (this._disposed) return;
    this._rafId = requestAnimationFrame(() => this._animate());
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this._disposed = true;
    if (this._rafId) cancelAnimationFrame(this._rafId);
    this._resizeObserver.disconnect();
    this._clearParts();
    this.controls.dispose();
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }

  _clearParts() {
    for (const rec of this.partRecords) {
      this.modelGroup.remove(rec.group);
      rec.mesh.geometry.dispose();
      rec.mesh.material.dispose();
      if (rec.edges) {
        rec.edges.geometry.dispose();
        rec.edges.material.dispose();
      }
    }
    this.partRecords = [];
  }

  setParts(parts, { resetCamera = false } = {}) {
    this._clearParts();

    for (const p of parts) {
      const geo = new THREE.BufferGeometry();
      geo.setAttribute("position", new THREE.BufferAttribute(p.positions, 3));
      geo.setIndex(new THREE.BufferAttribute(p.indices, 1));
      geo.computeVertexNormals();

      const color = new THREE.Color(p.color[0], p.color[1], p.color[2]);
      const isTransparent = p.opacity < 0.99;

      const mat = new THREE.MeshStandardMaterial({
        color,
        roughness: isTransparent ? 0.35 : 0.48,
        metalness: 0.08,
        transparent: isTransparent,
        opacity: p.opacity,
        depthWrite: !isTransparent,
        side: THREE.DoubleSide,
      });

      const mesh = new THREE.Mesh(geo, mat);
      const group = new THREE.Group();
      group.add(mesh);

      let edges = null;
      if (!isTransparent) {
        const edgeGeo = new THREE.EdgesGeometry(geo, 28);
        const edgeMat = new THREE.LineBasicMaterial({
          color: 0x0f172a,
          transparent: true,
          opacity: 0.45,
        });
        edges = new THREE.LineSegments(edgeGeo, edgeMat);
        edges.visible = this.showEdges;
        group.add(edges);
      }

      const asmOff = p.assembly_offset || [0, 0, 0];
      const expOff = p.exploded_offset || asmOff;
      const activeOff = this.exploded ? expOff : asmOff;
      group.position.set(activeOff[0], activeOff[1], activeOff[2]);

      if (!p.printable) {
        group.visible = this.showReference;
      }

      this.modelGroup.add(group);
      this.partRecords.push({
        meta: p,
        group,
        mesh,
        edges,
        asmOff,
        expOff,
      });
    }

    if (resetCamera || !this.hasFramedOnce) {
      this.setCameraPreset("iso");
      this.hasFramedOnce = true;
    }
  }

  setShowEdges(enabled) {
    this.showEdges = enabled;
    for (const rec of this.partRecords) {
      if (rec.edges) rec.edges.visible = enabled;
    }
  }

  setShowGrid(enabled) {
    this.showGrid = enabled;
    this.gridGroup.visible = enabled;
  }

  setShowReference(enabled) {
    this.showReference = enabled;
    for (const rec of this.partRecords) {
      if (!rec.meta.printable) rec.group.visible = enabled;
    }
  }

  setExploded(enabled) {
    this.exploded = enabled;
    for (const rec of this.partRecords) {
      const off = enabled ? rec.expOff : rec.asmOff;
      rec.group.position.set(off[0], off[1], off[2]);
    }
  }

  setCameraPreset(preset) {
    const box = new THREE.Box3();
    for (const rec of this.partRecords) {
      if (rec.group.visible) box.expandByObject(rec.group);
    }
    if (box.isEmpty()) {
      box.set(new THREE.Vector3(-50, -50, 0), new THREE.Vector3(50, 50, 50));
    }

    const center = new THREE.Vector3();
    const size = new THREE.Vector3();
    box.getCenter(center);
    box.getSize(size);

    const maxDim = Math.max(size.x, size.y, size.z, 30);
    const dist = maxDim * 1.95;

    this.controls.target.copy(center);

    if (preset === "top") {
      this.camera.up.set(0, 1, 0);
      this.camera.position.set(center.x, center.y, center.z + dist);
    } else if (preset === "front") {
      this.camera.up.set(0, 0, 1);
      this.camera.position.set(center.x, center.y - dist, center.z);
    } else if (preset === "side") {
      this.camera.up.set(0, 0, 1);
      this.camera.position.set(center.x + dist, center.y, center.z);
    } else {
      this.camera.up.set(0, 0, 1);
      this.camera.position.set(
        center.x + dist * 0.72,
        center.y - dist * 0.88,
        center.z + dist * 0.62
      );
    }

    this.camera.lookAt(center);
    this.controls.update();
  }
}

/**
 * Serialize a tessellated part (positions + triangle indices) directly into a
 * binary STL Blob in the browser for instant zero-WASM default downloads.
 */
export function buildBinaryStlFromMesh(positions, indices) {
  const triCount = Math.floor(indices.length / 3);
  const buffer = new ArrayBuffer(84 + triCount * 50);
  const view = new DataView(buffer);

  // 80-byte header + triangle count
  const header = "Exported from build123d web preview";
  for (let i = 0; i < header.length; i++) {
    view.setUint8(i, header.charCodeAt(i));
  }
  view.setUint32(80, triCount, true);

  let offset = 84;
  for (let t = 0; t < triCount; t++) {
    const i0 = indices[t * 3] * 3;
    const i1 = indices[t * 3 + 1] * 3;
    const i2 = indices[t * 3 + 2] * 3;

    const ax = positions[i0], ay = positions[i0 + 1], az = positions[i0 + 2];
    const bx = positions[i1], by = positions[i1 + 1], bz = positions[i1 + 2];
    const cx = positions[i2], cy = positions[i2 + 1], cz = positions[i2 + 2];

    const ux = bx - ax, uy = by - ay, uz = bz - az;
    const vx = cx - ax, vy = cy - ay, vz = cz - az;
    let nx = uy * vz - uz * vy;
    let ny = uz * vx - ux * vz;
    let nz = ux * vy - uy * vx;
    const len = Math.hypot(nx, ny, nz);
    if (len > 1e-9) {
      nx /= len; ny /= len; nz /= len;
    }

    view.setFloat32(offset, nx, true); offset += 4;
    view.setFloat32(offset, ny, true); offset += 4;
    view.setFloat32(offset, nz, true); offset += 4;

    view.setFloat32(offset, ax, true); offset += 4;
    view.setFloat32(offset, ay, true); offset += 4;
    view.setFloat32(offset, az, true); offset += 4;

    view.setFloat32(offset, bx, true); offset += 4;
    view.setFloat32(offset, by, true); offset += 4;
    view.setFloat32(offset, bz, true); offset += 4;

    view.setFloat32(offset, cx, true); offset += 4;
    view.setFloat32(offset, cy, true); offset += 4;
    view.setFloat32(offset, cz, true); offset += 4;

    view.setUint16(offset, 0, true); offset += 2;
  }

  return new Blob([buffer], { type: "model/stl" });
}
