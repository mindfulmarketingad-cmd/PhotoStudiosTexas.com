/* Homepage: show the top-rated studios near the visitor.
   1. /api/geo returns the approximate city and coordinates from Vercel's IP geolocation headers (no prompt).
   2. "Use my precise location" asks the browser for GPS/Wi-Fi location.
   3. ?near=<city-slug> forces a city (handy for testing).
   Nothing is stored on a server. */
(function () {
  "use strict";
  var grid = document.getElementById("near-grid");
  if (!grid) { return; }
  var title = document.getElementById("near-title");
  var link = document.getElementById("near-link");
  var bar = document.getElementById("near-bar");
  var note = document.getElementById("near-note");
  var precise = document.getElementById("near-precise");
  var select = document.getElementById("city-select");
  var MAX_TEXAS_MILES = 120;
  var indexPromise = null;

  function loadIndex() {
    if (!indexPromise) {
      indexPromise = fetch("/assets/geo-index.json").then(function (r) {
        if (!r.ok) { throw new Error("index " + r.status); }
        return r.json();
      });
    }
    return indexPromise;
  }

  function miles(lat1, lon1, lat2, lon2) {
    var rad = Math.PI / 180;
    var a = Math.pow(Math.sin((lat2 - lat1) * rad / 2), 2) +
      Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.pow(Math.sin((lon2 - lon1) * rad / 2), 2);
    return 2 * 3958.76 * Math.asin(Math.sqrt(Math.min(1, a)));
  }

  function esc(value) {
    return String(value).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function initials(name) {
    var words = String(name).replace(/[^A-Za-z0-9 ]/g, " ").split(/\s+/).filter(Boolean);
    return (words.slice(0, 2).map(function (w) { return w[0]; }).join("") || "PS").toUpperCase();
  }

  function nearestCity(data, lat, lon) {
    var best = -1, bestMiles = Infinity;
    data.cities.forEach(function (c, i) {
      var d = miles(lat, lon, c[2], c[3]);
      if (d < bestMiles) { bestMiles = d; best = i; }
    });
    return { index: best, miles: bestMiles };
  }

  function card(s, data, d) {
    var city = data.cities[s[2]][0];
    var img = s[7] ? '<img src="' + esc(s[7]) + '" alt="' + esc(s[0] + " in " + city + ", Texas") +
      '" width="800" height="500" loading="lazy" decoding="async" referrerpolicy="no-referrer" onerror="this.remove()">' : "";
    var tags = (s[9] || []).map(function (t) { return '<span class="tag tag-spec">' + esc(t) + "</span>"; }).join("");
    var noun = s[4] === 1 ? "review" : "reviews";
    return '<a class="studio-card" href="' + esc(s[1]) + '">' +
      '<div class="photo"><span aria-hidden="true">' + esc(initials(s[0])) + "</span>" + img + "</div>" +
      '<div class="card-body"><h3>' + esc(s[0]) + "</h3>" +
      '<p class="rating"><span class="stars" style="--r:' + s[3].toFixed(2) + '" aria-hidden="true"></span> <b>' +
      s[3].toFixed(1) + '</b> <span class="muted">(' + s[4].toLocaleString("en-US") + " " + noun + ")</span></p>" +
      '<p class="muted card-city">' + esc(city) + ", TX · " + (d < 1 ? "under 1 mi" : Math.round(d) + " mi") + " away</p>" +
      (tags ? '<div class="tags">' + tags + "</div>" : "") + "</div></a>";
  }

  function render(data, lat, lon, source, labelOverride) {
    var near = nearestCity(data, lat, lon);
    if (near.index < 0) { return false; }
    if (near.miles > MAX_TEXAS_MILES) {
      bar.hidden = false;
      note.textContent = source === "device"
        ? "You look to be outside Texas, so these are featured studios statewide. Pick a city above to see its studios."
        : "Showing featured studios statewide. In Texas? Use your precise location to see studios near you.";
      return false;
    }
    var city = data.cities[near.index];
    var radius = 25, picked = [];
    while (radius <= 100) {
      picked = [];
      data.studios.forEach(function (s) {
        var d = miles(lat, lon, s[5], s[6]);
        if (d <= radius) { picked.push({ s: s, d: d }); }
      });
      if (picked.length >= 8) { break; }
      radius *= 2;
    }
    picked.sort(function (a, b) { return b.s[8] - a.s[8] || a.d - b.d; });
    picked = picked.slice(0, 8);
    if (!picked.length) { return false; }
    var label = labelOverride || city[0];
    grid.innerHTML = picked.map(function (p) { return card(p.s, data, p.d); }).join("");
    title.textContent = "Top studios near " + label;
    link.href = city[1];
    link.textContent = "All " + city[4] + " " + city[0] + " studios";
    bar.hidden = false;
    note.textContent = (source === "device"
      ? "Based on your device location. "
      : source === "param" ? "Showing " + city[0] + ". "
      : "Based on your approximate location (" + label + "). ") +
      "Ranked by rating weighted by review count, within " + radius + " miles.";
    grid.setAttribute("data-near", city[1]);
    if (select && !select.value) {
      select.value = city[1];
      if (select.value !== city[1]) { select.value = ""; }
    }
    if (source === "device") { precise.hidden = true; }
    return true;
  }

  function fromIp() {
    var cached = null;
    try { cached = JSON.parse(sessionStorage.getItem("pst-geo") || "null"); } catch (e) { cached = null; }
    var geo = cached ? Promise.resolve(cached) : fetch("/api/geo", { cache: "no-store" }).then(function (r) {
      if (!r.ok) { throw new Error("geo " + r.status); }
      return r.json();
    }).then(function (g) {
      try { sessionStorage.setItem("pst-geo", JSON.stringify(g)); } catch (e) { /* private mode */ }
      return g;
    });
    return geo.then(function (g) {
      var lat = parseFloat(g.latitude), lon = parseFloat(g.longitude);
      if (!isFinite(lat) || !isFinite(lon)) {
        bar.hidden = false;
        note.textContent = "Showing featured studios statewide.";
        return;
      }
      return loadIndex().then(function (data) {
        var label = g.city && g.region === "TX" ? g.city : null;
        render(data, lat, lon, "ip", label);
      });
    });
  }

  precise.addEventListener("click", function () {
    if (!navigator.geolocation) {
      note.textContent = "Your browser does not share location. Pick a city above instead.";
      return;
    }
    precise.disabled = true;
    note.textContent = "Finding studios near you…";
    navigator.geolocation.getCurrentPosition(function (pos) {
      loadIndex().then(function (data) {
        render(data, pos.coords.latitude, pos.coords.longitude, "device");
        precise.disabled = false;
      });
    }, function () {
      precise.disabled = false;
      note.textContent = "Location permission was not given. Pick a city above instead.";
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 });
  });

  var forced = (location.search.match(/[?&]near=([a-z0-9-]+)/) || [])[1];
  if (forced) {
    loadIndex().then(function (data) {
      var hit = null;
      data.cities.forEach(function (c) { if (c[1] === "/tx/" + forced + "/") { hit = c; } });
      if (hit) { render(data, hit[2], hit[3], "param"); }
    });
  } else {
    fromIp().catch(function () {
      bar.hidden = false;
      note.textContent = "Showing featured studios statewide.";
    });
  }
})();
