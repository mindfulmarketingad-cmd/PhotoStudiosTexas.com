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

  var form = document.getElementById("order-form");
  if (form) {
    form.addEventListener("submit", function (event) {
      var endpoint = (config.ORDER_FORM_ENDPOINT || "").trim();
      if (/^https:\/\//.test(endpoint)) {
        form.action = endpoint;
        return;
      }
      var email = (config.CONTACT_EMAIL || "").trim();
      if (!email) {
        return;
      }
      event.preventDefault();
      var body = [];
      new FormData(form).forEach(function (value, key) {
        body.push(key + ": " + value);
      });
      var subject = form.getAttribute("data-subject") || "PhotoStudiosTexas order";
      window.location.href = "mailto:" + email
        + "?subject=" + encodeURIComponent(subject)
        + "&body=" + encodeURIComponent(body.join("\n"));
    });
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
