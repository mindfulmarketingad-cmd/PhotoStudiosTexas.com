(function () {
  var config = window.SITE_CONFIG || {};

  var orderButton = document.getElementById("order-now");
  var paymentLink = (config.STRIPE_PAYMENT_LINK || "").trim();
  if (orderButton && /^https:\/\//.test(paymentLink)) {
    orderButton.href = paymentLink;
    orderButton.target = "_blank";
    orderButton.rel = "noopener noreferrer";
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

  var searchInput = document.getElementById("studio-search");
  var cityJump = document.getElementById("city-jump");
  var results = document.getElementById("search-results");
  var cityCards = document.querySelectorAll("[data-city]");

  if (cityJump) {
    cityJump.addEventListener("change", function () {
      if (cityJump.value) {
        window.location.href = cityJump.value;
      }
    });
  }

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
