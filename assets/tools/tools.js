/* Free photo tools: resizer, compressor, cropper, format converter.
   Everything runs on a <canvas> in this tab. No file is uploaded. */
(function () {
  "use strict";
  var app = document.getElementById("tool-app");
  if (!app) { return; }
  var tool = app.getAttribute("data-tool");
  var input = document.getElementById("tool-file");
  var drop = app.querySelector(".tool-drop");
  var statusEl = document.getElementById("tool-status");
  var stage = document.getElementById("tool-stage");
  var output = document.getElementById("tool-output");
  var EXT = { "image/jpeg": "jpg", "image/png": "png", "image/webp": "webp" };
  var current = null; // { img, name, size, type }
  var lastUrls = [];

  function $(id) { return document.getElementById(id); }
  function status(text) { statusEl.textContent = text || ""; }
  function kb(bytes) {
    return bytes >= 1048576 ? (bytes / 1048576).toFixed(2) + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB";
  }
  function baseName(name) { return String(name || "image").replace(/\.[^.]+$/, "").replace(/[^\w.-]+/g, "-").slice(0, 60) || "image"; }
  function debounce(fn, ms) { var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); }; }

  function loadImage(file) {
    return new Promise(function (resolve, reject) {
      var url = URL.createObjectURL(file);
      var img = new Image();
      img.onload = function () { resolve(img); };
      img.onerror = function () { URL.revokeObjectURL(url); reject(new Error("This browser cannot open that file. Try a JPG, PNG, or WebP.")); };
      img.src = url;
    });
  }

  function canvasFor(w, h) {
    var c = document.createElement("canvas");
    c.width = Math.max(1, Math.round(w));
    c.height = Math.max(1, Math.round(h));
    return c;
  }

  // Draw with stepwise halving for clean downscaling.
  function drawScaled(src, sx, sy, sw, sh, w, h, fill) {
    var cur = src, cx = sx, cy = sy, cw = sw, ch = sh;
    while (cw / 2 >= w && ch / 2 >= h && cw > 2 && ch > 2) {
      var half = canvasFor(cw / 2, ch / 2);
      var hctx = half.getContext("2d");
      hctx.imageSmoothingQuality = "high";
      hctx.drawImage(cur, cx, cy, cw, ch, 0, 0, half.width, half.height);
      cur = half; cx = 0; cy = 0; cw = half.width; ch = half.height;
    }
    var out = canvasFor(w, h);
    var ctx = out.getContext("2d");
    if (fill) { ctx.fillStyle = fill; ctx.fillRect(0, 0, out.width, out.height); }
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.drawImage(cur, cx, cy, cw, ch, 0, 0, out.width, out.height);
    return out;
  }

  function toBlob(canvas, type, quality) {
    return new Promise(function (resolve, reject) {
      canvas.toBlob(function (blob) {
        if (blob) { resolve(blob); } else { reject(new Error("Could not encode the image.")); }
      }, type, quality);
    });
  }

  function clearOutput() {
    lastUrls.forEach(function (u) { URL.revokeObjectURL(u); });
    lastUrls = [];
    output.innerHTML = "";
  }

  function addResult(blob, name, meta) {
    var url = URL.createObjectURL(blob);
    lastUrls.push(url);
    var fig = document.createElement("figure");
    fig.className = "tool-result";
    fig.innerHTML = '<div class="tool-preview checker"><img alt="Result preview"></div>' +
      '<figcaption><span class="tool-meta"></span> <a class="btn btn-orange tool-download">Download</a></figcaption>';
    fig.querySelector("img").src = url;
    fig.querySelector(".tool-meta").textContent = meta;
    var a = fig.querySelector("a");
    a.href = url;
    a.download = name;
    a.textContent = "Download " + name.split(".").pop().toUpperCase();
    output.appendChild(fig);
    return fig;
  }

  // ---------------------------------------------------------------- resizer
  function setupResizer() {
    var w = $("rs-w"), h = $("rs-h"), lock = $("rs-lock"), fmt = $("rs-fmt");
    var run = debounce(function () {
      if (!current) { return; }
      var W = parseInt(w.value, 10), H = parseInt(h.value, 10);
      if (!(W > 0 && H > 0) || W > 12000 || H > 12000) { status("Enter a width and height between 1 and 12,000 px."); return; }
      var img = current.img;
      var type = fmt.value;
      var canvas = drawScaled(img, 0, 0, img.naturalWidth, img.naturalHeight, W, H, type === "image/jpeg" ? "#ffffff" : null);
      toBlob(canvas, type, 0.92).then(function (blob) {
        clearOutput();
        addResult(blob, baseName(current.name) + "-" + W + "x" + H + "." + EXT[type],
          img.naturalWidth + "×" + img.naturalHeight + " → " + W + "×" + H + " · " + kb(blob.size));
        status("Resized. Your image never left this device.");
      });
    }, 150);
    w.addEventListener("input", function () {
      if (current && lock.checked && w.value) { h.value = Math.max(1, Math.round(w.value * current.img.naturalHeight / current.img.naturalWidth)); }
      run();
    });
    h.addEventListener("input", function () {
      if (current && lock.checked && h.value) { w.value = Math.max(1, Math.round(h.value * current.img.naturalWidth / current.img.naturalHeight)); }
      run();
    });
    fmt.addEventListener("change", run);
    $("rs-presets").addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (!b || !current) { return; }
      var img = current.img;
      if (b.dataset.pct) {
        var p = Number(b.dataset.pct) / 100;
        w.value = Math.max(1, Math.round(img.naturalWidth * p));
        h.value = Math.max(1, Math.round(img.naturalHeight * p));
      } else {
        var parts = b.dataset.size.split("x");
        lock.checked = false;
        w.value = parts[0]; h.value = parts[1];
      }
      run();
    });
    return function onLoad() {
      w.value = Math.round(current.img.naturalWidth / 2) || 1;
      h.value = Math.round(current.img.naturalHeight / 2) || 1;
      run();
    };
  }

  // ---------------------------------------------------------------- compressor
  function setupCompressor() {
    var fmt = $("cp-fmt"), q = $("cp-q"), qv = $("cp-qv"), max = $("cp-max");
    var run = debounce(function () {
      if (!current) { return; }
      var img = current.img;
      var limit = Number(max.value) || 0;
      var scale = limit && Math.max(img.naturalWidth, img.naturalHeight) > limit ? limit / Math.max(img.naturalWidth, img.naturalHeight) : 1;
      var W = Math.round(img.naturalWidth * scale), H = Math.round(img.naturalHeight * scale);
      var type = fmt.value;
      var canvas = drawScaled(img, 0, 0, img.naturalWidth, img.naturalHeight, W, H, type === "image/jpeg" ? "#ffffff" : null);
      toBlob(canvas, type, Number(q.value) / 100).then(function (blob) {
        clearOutput();
        var saved = Math.round(100 * (1 - blob.size / current.size));
        addResult(blob, baseName(current.name) + "-compressed." + EXT[type],
          kb(current.size) + " → " + kb(blob.size) + (saved > 0 ? " (" + saved + "% smaller)" : " (no smaller, try a lower quality)") + " · " + W + "×" + H);
        status("Compressed in your browser. Nothing was uploaded.");
      });
    }, 150);
    q.addEventListener("input", function () { qv.textContent = q.value; run(); });
    fmt.addEventListener("change", run);
    max.addEventListener("change", run);
    return run;
  }

  // ---------------------------------------------------------------- cropper
  function setupCropper() {
    var ratios = $("cr-ratios"), fmt = $("cr-fmt");
    var ratio = 0, view = null, rect = null, drag = null, scale = 1;
    var canvas = document.createElement("canvas");
    canvas.className = "crop-canvas";
    canvas.setAttribute("aria-label", "Drag to choose the crop area");
    var ctx = canvas.getContext("2d");

    function fitRect() {
      var W = canvas.width, H = canvas.height;
      if (!ratio) { rect = { x: W * 0.05, y: H * 0.05, w: W * 0.9, h: H * 0.9 }; return; }
      var w = W * 0.9, h = w / ratio;
      if (h > H * 0.9) { h = H * 0.9; w = h * ratio; }
      rect = { x: (W - w) / 2, y: (H - h) / 2, w: w, h: h };
    }
    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(current.img, 0, 0, canvas.width, canvas.height);
      ctx.fillStyle = "rgba(17,17,17,0.55)";
      ctx.fillRect(0, 0, canvas.width, rect.y);
      ctx.fillRect(0, rect.y + rect.h, canvas.width, canvas.height - rect.y - rect.h);
      ctx.fillRect(0, rect.y, rect.x, rect.h);
      ctx.fillRect(rect.x + rect.w, rect.y, canvas.width - rect.x - rect.w, rect.h);
      ctx.strokeStyle = "#e85d04";
      ctx.lineWidth = 2;
      ctx.strokeRect(rect.x + 1, rect.y + 1, rect.w - 2, rect.h - 2);
    }
    function point(e) {
      var b = canvas.getBoundingClientRect();
      return { x: (e.clientX - b.left) * canvas.width / b.width, y: (e.clientY - b.top) * canvas.height / b.height };
    }
    function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
    var exportCrop = debounce(function () {
      if (!current || rect.w < 2 || rect.h < 2) { return; }
      var sx = rect.x / scale, sy = rect.y / scale, sw = rect.w / scale, sh = rect.h / scale;
      var type = fmt.value;
      var out = drawScaled(current.img, sx, sy, sw, sh, sw, sh, type === "image/jpeg" ? "#ffffff" : null);
      toBlob(out, type, 0.92).then(function (blob) {
        clearOutput();
        addResult(blob, baseName(current.name) + "-cropped." + EXT[type], out.width + "×" + out.height + " px · " + kb(blob.size));
        status("Drag on the photo to change the crop.");
      });
    }, 120);
    canvas.addEventListener("pointerdown", function (e) {
      if (!current) { return; }
      var p = point(e);
      canvas.setPointerCapture(e.pointerId);
      if (p.x > rect.x && p.x < rect.x + rect.w && p.y > rect.y && p.y < rect.y + rect.h) {
        drag = { mode: "move", ox: p.x - rect.x, oy: p.y - rect.y };
      } else {
        drag = { mode: "new", sx: p.x, sy: p.y };
      }
    });
    canvas.addEventListener("pointermove", function (e) {
      if (!drag) { return; }
      var p = point(e), W = canvas.width, H = canvas.height;
      if (drag.mode === "move") {
        rect.x = clamp(p.x - drag.ox, 0, W - rect.w);
        rect.y = clamp(p.y - drag.oy, 0, H - rect.h);
      } else {
        var x2 = clamp(p.x, 0, W), y2 = clamp(p.y, 0, H);
        var w = Math.abs(x2 - drag.sx), h = Math.abs(y2 - drag.sy);
        if (ratio) {
          if (w / h > ratio) { w = h * ratio; } else { h = w / ratio; }
        }
        var x = x2 < drag.sx ? drag.sx - w : drag.sx;
        var y = y2 < drag.sy ? drag.sy - h : drag.sy;
        if (w > 4 && h > 4) { rect = { x: clamp(x, 0, W - w), y: clamp(y, 0, H - h), w: w, h: h }; }
      }
      draw();
    });
    function end() { if (drag) { drag = null; exportCrop(); } }
    canvas.addEventListener("pointerup", end);
    canvas.addEventListener("pointercancel", end);
    ratios.addEventListener("click", function (e) {
      var b = e.target.closest("button");
      if (!b) { return; }
      ratios.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      ratio = Number(b.dataset.ratio) || 0;
      if (current) { fitRect(); draw(); exportCrop(); }
    });
    fmt.addEventListener("change", function () { if (current) { exportCrop(); } });
    return function onLoad() {
      var img = current.img;
      var maxW = Math.min(stage.clientWidth || 900, 900), maxH = 640;
      scale = Math.min(1, maxW / img.naturalWidth, maxH / img.naturalHeight);
      canvas.width = Math.max(1, Math.round(img.naturalWidth * scale));
      canvas.height = Math.max(1, Math.round(img.naturalHeight * scale));
      stage.innerHTML = "";
      stage.appendChild(canvas);
      fitRect();
      draw();
      exportCrop();
    };
  }

  // ---------------------------------------------------------------- converter
  function setupConverter() {
    var fmt = $("cv-fmt"), bg = $("cv-bg");
    var files = [];
    function run() {
      if (!files.length) { return; }
      clearOutput();
      var type = fmt.value;
      var jobs = files.map(function (f) {
        return loadImage(f).then(function (img) {
          var c = drawScaled(img, 0, 0, img.naturalWidth, img.naturalHeight, img.naturalWidth, img.naturalHeight,
            type === "image/jpeg" ? bg.value : null);
          return toBlob(c, type, 0.92).then(function (blob) {
            addResult(blob, baseName(f.name) + "." + EXT[type],
              f.name + " → " + EXT[type].toUpperCase() + " · " + img.naturalWidth + "×" + img.naturalHeight + " · " + kb(blob.size));
          });
        }).catch(function (err) { status(f.name + ": " + err.message); });
      });
      Promise.all(jobs).then(function () { status("Converted " + files.length + " file" + (files.length === 1 ? "" : "s") + " in your browser."); });
    }
    fmt.addEventListener("change", run);
    bg.addEventListener("change", run);
    return {
      multi: function (list) { files = list; run(); }
    };
  }

  var handlers = {
    "image-resizer": setupResizer,
    "image-compressor": setupCompressor,
    "image-cropper": setupCropper,
    "image-format-converter": setupConverter
  };
  if (!handlers[tool]) { return; }
  var onLoad = handlers[tool]();

  function handleFiles(list) {
    var arr = Array.prototype.slice.call(list || []).filter(function (f) { return /^image\//.test(f.type) || /\.(jpe?g|png|webp|gif|bmp|avif|heic)$/i.test(f.name); });
    if (!arr.length) { status("Please choose an image file."); return; }
    if (onLoad && onLoad.multi) { onLoad.multi(arr); return; }
    var file = arr[0];
    status("Opening " + file.name + "…");
    loadImage(file).then(function (img) {
      current = { img: img, name: file.name, size: file.size, type: file.type };
      app.classList.add("has-image");
      stage.hidden = tool !== "image-cropper";
      status(file.name + " · " + img.naturalWidth + "×" + img.naturalHeight + " · " + kb(file.size));
      onLoad();
    }).catch(function (err) { status(err.message); });
  }

  input.addEventListener("change", function () { handleFiles(input.files); });
  ["dragenter", "dragover"].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.add("is-over"); });
  });
  ["dragleave", "drop"].forEach(function (ev) {
    drop.addEventListener(ev, function (e) { e.preventDefault(); drop.classList.remove("is-over"); });
  });
  drop.addEventListener("drop", function (e) { handleFiles(e.dataTransfer && e.dataTransfer.files); });
})();
