/* Directory behavior: open-now status, hours highlight, city filter bar. No dependencies. */
(function () {
  "use strict";

  function parseHours(value) {
    var week = {};
    (value || "").split(";").forEach(function (part) {
      var pair = part.split("=");
      if (pair.length !== 2) { return; }
      week[pair[0]] = pair[1].split(",").map(function (range) {
        var bits = range.split("-");
        return [Number(bits[0]), Number(bits[1])];
      });
    });
    return week;
  }

  function nowIn(tz) {
    var map = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
    try {
      var parts = new Intl.DateTimeFormat("en-US", {
        timeZone: tz, weekday: "short", hour: "numeric", minute: "numeric", hourCycle: "h23"
      }).formatToParts(new Date());
      var day = 0, hour = 0, minute = 0;
      parts.forEach(function (p) {
        if (p.type === "weekday") { day = map[p.value]; }
        if (p.type === "hour") { hour = Number(p.value) % 24; }
        if (p.type === "minute") { minute = Number(p.value); }
      });
      return { day: day, minutes: hour * 60 + minute };
    } catch (error) {
      var d = new Date();
      return { day: d.getDay(), minutes: d.getHours() * 60 + d.getMinutes() };
    }
  }

  function fmt(minutes) {
    minutes = minutes % 1440;
    var h = Math.floor(minutes / 60), m = minutes % 60;
    var suffix = h < 12 ? "AM" : "PM";
    var h12 = h % 12 || 12;
    return h12 + (m ? ":" + (m < 10 ? "0" : "") + m : "") + " " + suffix;
  }

  /* returns {open: bool, text: string} */
  function status(week, tz) {
    var now = nowIn(tz);
    var today = week[String(now.day)] || [];
    var yesterday = week[String((now.day + 6) % 7)] || [];
    var i, range;
    for (i = 0; i < yesterday.length; i += 1) {
      range = yesterday[i];
      if (range[1] > 1440 && now.minutes < range[1] - 1440) {
        return { open: true, text: "Open now · closes " + fmt(range[1]) };
      }
    }
    for (i = 0; i < today.length; i += 1) {
      range = today[i];
      if (now.minutes >= range[0] && now.minutes < range[1]) {
        if (range[0] === 0 && range[1] === 1440) { return { open: true, text: "Open 24 hours today" }; }
        return { open: true, text: "Open now · closes " + fmt(range[1]) };
      }
    }
    for (i = 0; i < today.length; i += 1) {
      if (now.minutes < today[i][0]) {
        return { open: false, text: "Closed now · opens " + fmt(today[i][0]) };
      }
    }
    return { open: false, text: "Closed now" };
  }

  /* studio page: highlight today's row and print the status */
  var table = document.querySelector(".hours-table[data-hours]");
  if (table) {
    var week = parseHours(table.getAttribute("data-hours"));
    var tz = table.getAttribute("data-tz") || "America/Chicago";
    var now = nowIn(tz);
    var row = table.querySelector('tr[data-day="' + now.day + '"]');
    if (row) { row.classList.add("is-today"); }
    var line = document.getElementById("open-status");
    if (line) {
      var s = status(week, tz);
      line.textContent = s.text;
      line.className = "open-status-line " + (s.open ? "is-open" : "is-closed");
      line.hidden = false;
    }
  }

  /* cards: small open/closed line */
  var cards = Array.prototype.slice.call(document.querySelectorAll(".studio-card"));
  var openNow = {};
  cards.forEach(function (card, i) {
    var hours = card.getAttribute("data-hours");
    var line = card.querySelector(".open-status");
    if (!hours || !line || card.querySelector(".badge")) { return; }
    var s = status(parseHours(hours), card.getAttribute("data-tz") || "America/Chicago");
    line.textContent = s.text;
    line.className = "open-status " + (s.open ? "is-open" : "is-closed");
    line.hidden = false;
    card.setAttribute("data-open", s.open ? "1" : "0");
  });

  /* city filter bar */
  var bar = document.getElementById("filter-bar");
  var grid = document.getElementById("studio-grid");
  if (!bar || !grid) { return; }
  bar.hidden = false;

  var q = document.getElementById("f-q");
  var minRating = document.getElementById("f-rating");
  var sort = document.getElementById("f-sort");
  var fOpen = document.getElementById("f-open");
  var fHours = document.getElementById("f-hours");
  var fSite = document.getElementById("f-site");
  var fCity = document.getElementById("f-city");
  var count = document.getElementById("f-count");
  var none = document.getElementById("no-results");
  var chips = Array.prototype.slice.call(bar.querySelectorAll(".fchip"));
  var total = cards.length;

  function selectedTags() {
    return chips.filter(function (c) { return c.getAttribute("aria-pressed") === "true"; })
      .map(function (c) { return c.getAttribute("data-tag"); });
  }

  function apply() {
    var query = q.value.trim().toLowerCase();
    var min = Number(minRating.value) || 0;
    var tags = selectedTags();
    var shown = 0;
    cards.forEach(function (card) {
      var ok = true;
      if (query && card.getAttribute("data-name").indexOf(query) === -1) { ok = false; }
      if (ok && fCity && fCity.value && card.getAttribute("data-city") !== fCity.value) { ok = false; }
      if (ok && min && Number(card.getAttribute("data-rating")) < min) { ok = false; }
      if (ok && fHours.checked && card.getAttribute("data-has-hours") !== "1") { ok = false; }
      if (ok && fSite.checked && card.getAttribute("data-site") !== "1") { ok = false; }
      if (ok && fOpen.checked && card.getAttribute("data-open") !== "1") { ok = false; }
      if (ok && tags.length) {
        var have = (card.getAttribute("data-tags") || "").split(" ");
        for (var i = 0; i < tags.length; i += 1) {
          if (have.indexOf(tags[i]) === -1) { ok = false; break; }
        }
      }
      card.hidden = !ok;
      if (ok) { shown += 1; }
    });
    var mode = sort.value;
    var ordered = cards.slice().sort(function (a, b) {
      if (mode === "city") {
        var ca = a.getAttribute("data-city") || "", cb = b.getAttribute("data-city") || "";
        if (ca !== cb) { return ca < cb ? -1 : 1; }
        return Number(a.getAttribute("data-index")) - Number(b.getAttribute("data-index"));
      }
      if (mode === "name") { return a.getAttribute("data-name") < b.getAttribute("data-name") ? -1 : 1; }
      if (mode === "reviews") {
        return Number(b.getAttribute("data-reviews")) - Number(a.getAttribute("data-reviews"))
          || Number(a.getAttribute("data-index")) - Number(b.getAttribute("data-index"));
      }
      return Number(a.getAttribute("data-index")) - Number(b.getAttribute("data-index"));
    });
    ordered.forEach(function (card) { grid.appendChild(card); });
    count.textContent = shown === total
      ? "Showing all " + total + (total === 1 ? " studio" : " studios")
      : "Showing " + shown + " of " + total + " studios";
    none.hidden = shown !== 0;
  }

  function reset() {
    q.value = ""; minRating.value = "0"; sort.value = "rating";
    fOpen.checked = false; fHours.checked = false; fSite.checked = false;
    if (fCity) { fCity.value = ""; }
    chips.forEach(function (c) { c.setAttribute("aria-pressed", "false"); });
    apply();
  }

  chips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      chip.setAttribute("aria-pressed", chip.getAttribute("aria-pressed") === "true" ? "false" : "true");
      apply();
    });
  });
  [q, minRating, sort, fOpen, fHours, fSite, fCity].forEach(function (el) {
    if (!el) { return; }
    el.addEventListener("input", apply);
    el.addEventListener("change", apply);
  });
  document.getElementById("f-reset").addEventListener("click", reset);
  var reset2 = document.getElementById("f-reset-2");
  if (reset2) { reset2.addEventListener("click", reset); }

  /* ?tag=headshots deep link support */
  var params = new URLSearchParams(window.location.search);
  (params.get("tag") || "").split(",").forEach(function (tag) {
    chips.forEach(function (c) { if (c.getAttribute("data-tag") === tag) { c.setAttribute("aria-pressed", "true"); } });
  });
  if (fCity && params.get("city")) { fCity.value = params.get("city"); if (fCity.value !== params.get("city")) { fCity.value = ""; } }
  apply();
})();
