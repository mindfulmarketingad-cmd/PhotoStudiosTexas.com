/* Free image background remover. Runs an open-source segmentation model in the browser with
   Transformers.js (ONNX Runtime Web). The photo never leaves the device; only the model files are
   downloaded (from the Hugging Face CDN) and then cached by the browser.
   Models: MODNet (Xenova/modnet, Apache-2.0, portraits) and U^2-Netp (Apache-2.0, any subject). */
const TRANSFORMERS = "https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.8.1";
const ORT = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/ort.min.mjs";
const MODELS = {
  people: { id: "Xenova/modnet", dtype: "q8", input: "input", output: "output" },
  // U^2-Netp salient-object model (Apache-2.0), exported by rembg. Run directly with ONNX Runtime Web.
  any: { url: "https://huggingface.co/BritishWerewolf/U-2-Netp/resolve/main/onnx/model.onnx", size: 320, input: "input.1", output: "1959" },
};

const app = document.getElementById("tool-app");
const fileInput = document.getElementById("tool-file");
const drop = app.querySelector(".tool-drop");
const statusEl = document.getElementById("tool-status");
const stage = document.getElementById("tool-stage");
const output = document.getElementById("tool-output");
const runBtn = document.getElementById("bg-run");
const modelSel = document.getElementById("bg-model");
const fillSel = document.getElementById("bg-fill");
const colorWrap = document.getElementById("bg-color-wrap");
const colorInput = document.getElementById("bg-color");

let lib = null;
const loaded = {};
let current = null; // { file, img }
let cutout = null; // canvas with transparent background
let resultUrl = null;

const status = (t) => { statusEl.textContent = t || ""; };
const baseName = (n) => String(n || "image").replace(/\.[^.]+$/, "").replace(/[^\w.-]+/g, "-").slice(0, 60) || "image";

async function getModel(key) {
  if (loaded[key]) return loaded[key];
  const cfg = MODELS[key];
  if (key === "any") {
    status("Loading the AI model…");
    const ort = await import(ORT);
    ort.env.wasm.wasmPaths = "https://cdn.jsdelivr.net/npm/onnxruntime-web@1.22.0/dist/";
    const res = await fetch(cfg.url);
    if (!res.ok) throw new Error(`model download failed (${res.status})`);
    const buf = new Uint8Array(await res.arrayBuffer());
    const session = await ort.InferenceSession.create(buf, { executionProviders: ["wasm"] });
    loaded[key] = { ort, session, cfg };
    return loaded[key];
  }
  if (!lib) {
    status("Loading the AI library…");
    lib = await import(TRANSFORMERS);
    lib.env.allowLocalModels = false;
  }
  const progress = (p) => {
    if (p.status === "progress" && p.file && /\.onnx$/.test(p.file) && p.total) {
      status(`Downloading the AI model… ${Math.round((100 * p.loaded) / p.total)}% (first time only)`);
    }
  };
  const [model, processor] = await Promise.all([
    lib.AutoModel.from_pretrained(cfg.id, { dtype: cfg.dtype, device: "wasm", progress_callback: progress }),
    lib.AutoProcessor.from_pretrained(cfg.id),
  ]);
  loaded[key] = { model, processor, cfg };
  return loaded[key];
}

// Returns an alpha mask (Uint8ClampedArray, one byte per pixel) at the image's full size.
async function maskFor(key, img, W, H) {
  const m = await getModel(key);
  status("Removing the background…");
  await new Promise((r) => setTimeout(r, 30));
  if (key === "any") {
    const S = m.cfg.size;
    const c = document.createElement("canvas");
    c.width = S; c.height = S;
    const cx = c.getContext("2d");
    cx.imageSmoothingQuality = "high";
    cx.drawImage(img, 0, 0, S, S);
    const px = cx.getImageData(0, 0, S, S).data;
    const mean = [0.485, 0.456, 0.406], std = [0.229, 0.224, 0.225];
    let maxv = 1;
    for (let i = 0; i < px.length; i += 4) maxv = Math.max(maxv, px[i], px[i + 1], px[i + 2]);
    const data = new Float32Array(3 * S * S);
    for (let i = 0, p = 0; i < px.length; i += 4, p++) {
      for (let ch = 0; ch < 3; ch++) data[ch * S * S + p] = (px[i + ch] / maxv - mean[ch]) / std[ch];
    }
    const tensor = new m.ort.Tensor("float32", data, [1, 3, S, S]);
    const out = await m.session.run({ [m.cfg.input]: tensor });
    const pred = out[m.cfg.output].data;
    let lo = Infinity, hi = -Infinity;
    for (let i = 0; i < S * S; i++) { lo = Math.min(lo, pred[i]); hi = Math.max(hi, pred[i]); }
    const small = document.createElement("canvas");
    small.width = S; small.height = S;
    const sctx = small.getContext("2d");
    const sm = sctx.createImageData(S, S);
    for (let i = 0; i < S * S; i++) {
      const v = Math.round((255 * (pred[i] - lo)) / (hi - lo || 1));
      sm.data[4 * i] = sm.data[4 * i + 1] = sm.data[4 * i + 2] = v;
      sm.data[4 * i + 3] = 255;
    }
    sctx.putImageData(sm, 0, 0);
    const big = document.createElement("canvas");
    big.width = W; big.height = H;
    const bctx = big.getContext("2d");
    bctx.imageSmoothingQuality = "high";
    bctx.drawImage(small, 0, 0, W, H);
    const bd = bctx.getImageData(0, 0, W, H).data;
    const alpha = new Uint8ClampedArray(W * H);
    for (let i = 0; i < W * H; i++) alpha[i] = bd[4 * i];
    return alpha;
  }
  const image = await lib.RawImage.fromURL(img.src);
  const { pixel_values } = await m.processor(image);
  const result = await m.model({ [m.cfg.input]: pixel_values });
  const maskImg = await lib.RawImage.fromTensor(result[m.cfg.output][0].mul(255).to("uint8")).resize(W, H);
  const step = maskImg.channels || 1;
  const alpha = new Uint8ClampedArray(W * H);
  for (let i = 0; i < W * H; i++) alpha[i] = maskImg.data[i * step];
  return alpha;
}

function loadImage(file) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("This browser cannot open that file. Try a JPG, PNG, or WebP."));
    img.src = URL.createObjectURL(file);
  });
}

function compose() {
  if (!cutout) return;
  const fill = fillSel.value === "custom" ? colorInput.value : fillSel.value;
  const out = document.createElement("canvas");
  out.width = cutout.width;
  out.height = cutout.height;
  const ctx = out.getContext("2d");
  if (fill) { ctx.fillStyle = fill; ctx.fillRect(0, 0, out.width, out.height); }
  ctx.drawImage(cutout, 0, 0);
  out.toBlob((blob) => {
    if (resultUrl) URL.revokeObjectURL(resultUrl);
    resultUrl = URL.createObjectURL(blob);
    const name = `${baseName(current.file.name)}-no-background.png`;
    output.innerHTML = `<div class="bg-compare">
  <figure><figcaption>Original</figcaption><div class="tool-preview"><img alt="Original photo" src="${current.img.src}"></div></figure>
  <figure><figcaption>Background removed</figcaption><div class="tool-preview checker"><img id="bg-result" alt="Photo with the background removed" src="${resultUrl}"></div></figure>
</div>
<p class="tool-result-actions"><a class="btn btn-orange" id="bg-download" download="${name}" href="${resultUrl}">Download PNG</a>
<span class="muted">${out.width}×${out.height} · ${(blob.size / 1024).toFixed(0)} KB</span></p>`;
  }, "image/png");
}

async function run() {
  if (!current) return;
  runBtn.disabled = true;
  const key = modelSel.value;
  const t0 = performance.now();
  try {
    const W = current.img.naturalWidth, H = current.img.naturalHeight;
    const alpha = await maskFor(key, current.img, W, H);
    const canvas = document.createElement("canvas");
    canvas.width = W;
    canvas.height = H;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(current.img, 0, 0, W, H);
    const pixels = ctx.getImageData(0, 0, W, H);
    for (let i = 0, j = 0; i < pixels.data.length; i += 4, j++) pixels.data[i + 3] = alpha[j];
    ctx.putImageData(pixels, 0, 0);
    cutout = canvas;
    compose();
    app.dataset.state = "done";
    status(`Done in ${((performance.now() - t0) / 1000).toFixed(1)} s. Your photo never left this device.`);
  } catch (err) {
    console.error(err);
    app.dataset.state = "error";
    status(`Something went wrong: ${err && err.message ? err.message : err}. Try the other model or a smaller photo.`);
  } finally {
    runBtn.disabled = false;
  }
}

async function handle(files) {
  const file = Array.from(files || []).find((f) => /^image\//.test(f.type) || /\.(jpe?g|png|webp)$/i.test(f.name));
  if (!file) { status("Please choose an image file."); return; }
  try {
    const img = await loadImage(file);
    current = { file, img };
    cutout = null;
    output.innerHTML = "";
    stage.hidden = true;
    runBtn.disabled = false;
    app.classList.add("has-image");
    run();
  } catch (err) {
    status(err.message);
  }
}

fileInput.addEventListener("change", () => handle(fileInput.files));
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("is-over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("is-over"); }));
drop.addEventListener("drop", (e) => handle(e.dataTransfer && e.dataTransfer.files));
runBtn.addEventListener("click", run);
modelSel.addEventListener("change", () => { if (current) run(); });
fillSel.addEventListener("change", () => { colorWrap.hidden = fillSel.value !== "custom"; compose(); });
colorInput.addEventListener("input", compose);
status("Choose a photo to start. The AI model downloads the first time you use it.");

