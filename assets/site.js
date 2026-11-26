(function () {
  var config = window.SITE_CONFIG || {};

  var orderButton = document.getElementById("order-now");
  if (orderButton) {
    var paymentKey = orderButton.getAttribute("data-payment-key") || "STRIPE_PAYMENT_LINK";
    var paymentLink = (config[paymentKey] || "").trim();
    if (/^https:\/\//.test(paymentLink)) {
      orderButton.href = paymentLink;
      orderButton.target = "_blank";
      orderButton.rel = "noopener noreferrer";
    }
  }

  // ---- Forms: send to /api/submit (emails the site owner). Optional photo upload to Vercel Blob. ----
  var MAX_FILES = 12;
  var MAX_BYTES = 25 * 1024 * 1024;
  var EXT_TYPES = {
    jpg: "image/jpeg", jpeg: "image/jpeg", png: "image/png", webp: "image/webp", gif: "image/gif",
    heic: "image/heic", heif: "image/heif", tif: "image/tiff", tiff: "image/tiff", bmp: "image/bmp",
    avif: "image/avif", dng: "image/x-adobe-dng", psd: "image/vnd.adobe.photoshop", zip: "application/zip"
  };
  var blobLoader = null;

  function loadBlobClient() {
    if (window.PSTUpload) { return Promise.resolve(); }
    if (!blobLoader) {
      blobLoader = new Promise(function (resolve, reject) {
        var tag = document.createElement("script");
        tag.src = "/assets/blob-upload.js";
        tag.onload = resolve;
        tag.onerror = function () { reject(new Error("Could not load the uploader.")); };
        document.head.appendChild(tag);
      });
    }
    return blobLoader;
  }

  function extOf(name) {
    var m = /\.([A-Za-z0-9]+)$/.exec(name || "");
    return m ? m[1].toLowerCase() : "";
  }

  function fileType(file) {
    return file.type || EXT_TYPES[extOf(file.name)] || "";
  }

  function fmtSize(bytes) {
    return bytes >= 1048576 ? (bytes / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(bytes / 1024)) + " KB";
  }

  function initForm(form) {
    var status = form.querySelector(".form-status");
    var fileInput = form.querySelector('input[type="file"]');
    var list = form.querySelector(".file-list");
    var button = form.querySelector('button[type="submit"]');
    var pageField = form.querySelector('input[name="page"]');
    if (pageField) { pageField.value = window.location.href.split("#")[0]; }

    function say(message, kind) {
      if (!status) { return; }
      status.textContent = message;
      status.className = "form-status" + (kind ? " is-" + kind : "");
    }

    function validFiles() {
      var files = fileInput ? Array.prototype.slice.call(fileInput.files || []) : [];
      if (files.length > MAX_FILES) { return { error: "Please choose " + MAX_FILES + " files or fewer." }; }
      for (var i = 0; i < files.length; i += 1) {
        if (files[i].size > MAX_BYTES) { return { error: files[i].name + " is over 25 MB. Send a smaller copy or paste a share link." }; }
        if (!fileType(files[i])) { return { error: files[i].name + " is not a supported photo type." }; }
      }
      return { files: files };
    }

    if (fileInput && list) {
      fileInput.addEventListener("change", function () {
        var result = validFiles();
        list.innerHTML = "";
        if (result.error) { say(result.error, "error"); return; }
        say("");
        result.files.forEach(function (file) {
          var li = document.createElement("li");
          li.textContent = file.name + " (" + fmtSize(file.size) + ")";
          list.appendChild(li);
        });
      });
    }

    form.addEventListener("submit", function (event) {
      if (!window.fetch || !window.FormData) { return; }
      event.preventDefault();
      var result = validFiles();
      if (result.error) { say(result.error, "error"); return; }
      var data = new FormData(form);
      var payload = {};
      data.forEach(function (value, key) {
        if (key !== "photos" && typeof value === "string") { payload[key] = value; }
      });
      var requestField = form.querySelector('select[name="request"]');
      if (requestField && /^Remove/i.test(requestField.value)) { payload.kind = "removal"; }
      button.disabled = true;
      var files = result.files;
      var uploaded = [];
      var chain = Promise.resolve();
      if (files.length) {
        chain = loadBlobClient().then(function () {
          var step = Promise.resolve();
          files.forEach(function (file, index) {
            step = step.then(function () {
              say("Uploading photo " + (index + 1) + " of " + files.length + "…", "info");
              var safe = file.name.replace(/[^A-Za-z0-9._-]+/g, "_").slice(-100) || "photo.jpg";
              return window.PSTUpload.upload("orders/" + safe, file, {
                access: "public",
                handleUploadUrl: "/api/upload/",
                contentType: fileType(file),
                multipart: file.size > 8 * 1024 * 1024
              }).then(function (blob) {
                uploaded.push({ url: blob.url, name: file.name, size: file.size });
              });
            });
          });
          return step;
        });
      }
      chain.then(function () {
        say("Sending…", "info");
        payload.files = uploaded;
        return fetch("/api/submit/", {
          method: "POST",
          headers: { "Content-Type": "application/json", "Accept": "application/json" },
          body: JSON.stringify(payload)
        });
      }).then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (json) {
          if (!response.ok || !json.ok) { throw new Error(json.error || "Something went wrong."); }
        });
      }).then(function () {
        form.reset();
        if (list) { list.innerHTML = ""; }
        say("Thank you. We got it and will reply by email, usually within 2 business days.", "ok");
        button.disabled = false;
      }).catch(function (err) {
        say((err && err.message ? err.message : "Something went wrong.") + " If it keeps happening, try again in a minute.", "error");
        button.disabled = false;
      });
    });
  }

  Array.prototype.forEach.call(document.querySelectorAll("form[data-pst-form]"), initForm);

  // Claim / removal page: prefill from the studio page link.
  var claim = document.getElementById("claim-form");
  if (claim) {
    var q = new URLSearchParams(window.location.search);
    var studioName = q.get("studio");
    var studioUrl = q.get("url");
    if (studioName) { claim.elements.studio_name.value = studioName; }
    if (studioUrl && studioUrl.charAt(0) === "/") { claim.elements.studio_url.value = window.location.origin + studioUrl; }
    if (q.get("type") === "removal") { claim.elements.request.value = "Remove this listing"; }
  }

  function initLightbox() {
    var box = document.createElement("div");
    box.className = "lightbox";
    box.hidden = true;
    box.setAttribute("role", "dialog");
    box.setAttribute("aria-modal", "true");
    box.setAttribute("aria-label", "Enlarged before and after example");
    box.innerHTML = '<div class="lightbox-dialog">'
      + '<button type="button" class="lightbox-close" aria-label="Close">&times;</button>'
      + '<img alt="">'
      + '<p class="lightbox-caption"></p>'
      + '</div>';
    document.body.appendChild(box);
    var img = box.querySelector("img");
    var captionEl = box.querySelector(".lightbox-caption");
    var closeBtn = box.querySelector(".lightbox-close");
    var lastFocus = null;

    function close() {
      if (box.hidden) {
        return;
      }
      box.hidden = true;
      document.body.classList.remove("lightbox-open");
      img.removeAttribute("src");
      if (lastFocus && typeof lastFocus.focus === "function") {
        lastFocus.focus();
      }
    }

    function open(href, alt, captionText) {
      lastFocus = document.activeElement;
      img.src = href;
      img.alt = alt || "";
      captionEl.textContent = captionText || "";
      box.hidden = false;
      document.body.classList.add("lightbox-open");
      closeBtn.focus();
    }

    document.addEventListener("click", function (event) {
      var link = event.target.closest("a[data-lightbox]");
      if (!link) {
        return;
      }
      event.preventDefault();
      var thumb = link.querySelector("img");
      open(
        link.getAttribute("href"),
        thumb ? thumb.getAttribute("alt") : "",
        link.getAttribute("data-caption") || ""
      );
    });

    box.addEventListener("click", function (event) {
      if (event.target === box || event.target === closeBtn) {
        close();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        close();
      }
    });
  }

  if (document.querySelector("a[data-lightbox]")) {
    initLightbox();
  }

  var cityForm = document.getElementById("hero-city-search");
  var cityInput = document.getElementById("city-search");
  var cityPathsEl = document.getElementById("city-paths");
  var cityPaths = {};
  if (cityPathsEl) {
    try {
      cityPaths = JSON.parse(cityPathsEl.textContent || "{}");
    } catch (error) {
      cityPaths = {};
    }
  }

  function resolveCity(raw) {
    var query = String(raw || "").trim().toLowerCase();
    if (!query) {
      return "";
    }
    if (cityPaths[query]) {
      return cityPaths[query];
    }
    var matches = [];
    Object.keys(cityPaths).forEach(function (name) {
      if (name.indexOf(query) === 0) {
        matches.push(cityPaths[name]);
      }
    });
    return matches.length === 1 ? matches[0] : "";
  }

  function goToCity(raw) {
    var path = resolveCity(raw);
    if (path) {
      window.location.href = path;
      return true;
    }
    return false;
  }

  if (cityForm && cityInput) {
    cityForm.addEventListener("submit", function (event) {
      if (goToCity(cityInput.value)) {
        event.preventDefault();
      }
    });
    cityInput.addEventListener("change", function () {
      goToCity(cityInput.value);
    });
  }

  var cityJump = document.getElementById("city-jump");
  if (cityJump) {
    cityJump.addEventListener("change", function () {
      if (cityJump.value) {
        window.location.href = cityJump.value;
      }
    });
  }

  var searchInput = document.getElementById("studio-search");
  var results = document.getElementById("search-results");
  var cityCards = document.querySelectorAll("[data-city]");

  if (!searchInput || !results) {
    return;
  }

  var studios = [];
  var loaded = false;
  fetch("/assets/search-index.json")
    .then(function (response) { return response.json(); })
    .then(function (data) {
      studios = data;
      loaded = true;
      render();
    })
    .catch(function () {
      results.textContent = "Search is unavailable. Browse the city list below.";
    });

  function render() {
    var query = searchInput.value.trim().toLowerCase();
    cityCards.forEach(function (card) {
      var name = (card.getAttribute("data-city") || "").toLowerCase();
      card.hidden = Boolean(query) && name.indexOf(query) === -1;
    });
    if (!loaded || query.length < 2) {
      if (query.length < 2) {
        results.innerHTML = "";
      }
      return;
    }
    var matches = [];
    var total = 0;
    for (var index = 0; index < studios.length; index += 1) {
      var studio = studios[index];
      var haystack = (studio.name + " " + studio.city).toLowerCase();
      if (haystack.indexOf(query) === -1) {
        continue;
      }
      total += 1;
      if (matches.length < 40) {
        matches.push(studio);
      }
    }
    if (!total) {
      results.innerHTML = "<p>No studios match that search.</p>";
      return;
    }
    var html = matches.map(function (studio) {
      var meta = studio.city;
      if (studio.rating != null) {
        meta += " · " + Number(studio.rating).toFixed(1);
        if (studio.reviews) {
          meta += " (" + studio.reviews + ")";
        }
      }
      if (studio.closed) {
        meta += " · Temporarily closed";
      }
      return '<a href="' + studio.url + '"><span>' + escapeHtml(studio.name) + '</span><span class="muted">' + escapeHtml(meta) + "</span></a>";
    }).join("");
    if (total > matches.length) {
      html += "<p class=\"muted\">Showing " + matches.length + " of " + total + " matches.</p>";
    }
    results.innerHTML = html;
  }

  function escapeHtml(value) {
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  searchInput.addEventListener("input", render);
})();
