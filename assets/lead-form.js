(function () {
  // Listing-card "Book Now" buttons sit inside the card link: send them to the studio page's booking form.
  document.addEventListener("click", function (event) {
    var cta = event.target.closest ? event.target.closest("[data-book]") : null;
    if (!cta) { return; }
    var card = cta.closest("a.studio-card");
    if (!card) { return; }
    event.preventDefault();
    window.location.href = card.getAttribute("href").split("#")[0] + "#book";
  });

  var today = new Date();
  var iso = today.getFullYear() + "-" + ("0" + (today.getMonth() + 1)).slice(-2) + "-" + ("0" + today.getDate()).slice(-2);
  Array.prototype.forEach.call(document.querySelectorAll("input[data-min-today]"), function (input) { input.min = iso; });

  Array.prototype.forEach.call(document.querySelectorAll("form[data-lead-form]"), function (form) {
    var status = form.querySelector(".form-status");
    var button = form.querySelector('button[type="submit"]');
    function say(message, kind) {
      if (!status) { return; }
      status.textContent = message;
      status.className = "form-status" + (kind ? " is-" + kind : "");
    }
    form.addEventListener("submit", function (event) {
      if (!window.fetch) { return; }
      event.preventDefault();
      if (!form.checkValidity()) { form.reportValidity(); return; }
      var payload = {};
      new FormData(form).forEach(function (value, key) {
        if (typeof value === "string") { payload[key] = value; }
      });
      button.disabled = true;
      say("Sending…", "info");
      fetch("/api/lead/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify(payload)
      }).then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (json) {
          if (!response.ok || !json.ok) { throw new Error(json.error || "Something went wrong."); }
        });
      }).then(function () {
        form.reset();
        say("Thank you. Your booking request was sent, and we will follow up by email soon.", "ok");
        button.disabled = false;
      }).catch(function (err) {
        say((err && err.message ? err.message : "Something went wrong.") + " If it keeps happening, try again in a minute.", "error");
        button.disabled = false;
      });
    });
  });
})();
