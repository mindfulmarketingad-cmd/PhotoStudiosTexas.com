"""Book Now lead form for PhotoStudiosTexas.com (studio pages, homepage, listing-card CTA).

Mixed into build.Site. Stdlib only. Posts to /api/lead/ (api/lead.js), which stores the
lead in the shared general leads Supabase table and emails the owner. The listing's own
contact details (phone, email, website, booking and social links) are never published;
this form is the only way to reach a studio from this site.
"""

from __future__ import annotations

import html
import re

CTA_LABEL = "Book Now"

# Phone numbers, emails and URLs are stripped from any studio-supplied free text we display.
_PHONE = re.compile(r"(?<![\w$])(?:\+?1[\s.\-]?)?(?:\(\d{3}\)|\d{3})[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)")
_EMAIL = re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+")
_URL = re.compile(r"(?:https?://|www\.)\S+|\b[\w\-]+\.(?:com|net|org|co|us|biz|info|photo|photography|studio|pics)\b(?:/\S*)?", re.I)


def scrub_contact(text: str) -> str:
    """Remove phone numbers, emails and web addresses from studio-written text."""
    if not text:
        return text
    out = _EMAIL.sub("", text)
    out = _URL.sub("", out)
    out = _PHONE.sub("", out)
    out = re.sub(r"\b(?:call|text|email|e-mail|phone|visit|website|web|contact us at|reach us at)\s*(?:us\s*)?(?:at|:|-)?\s*(?=[,.;!)]|$)", "", out, flags=re.I)
    out = re.sub(r"\(\s*\)", "", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    out = re.sub(r"\s+([,.;!?])", r"\1", out)
    return out.strip(" ,;-|")


def _esc(value) -> str:
    return "" if value is None else html.escape(str(value), quote=True)


class LeadMixin:
    def lead_service_options(self, selected: str = "") -> str:
        self.prepare_categories()
        labels = [c["label"] for c in self.categories]
        labels += ["Other / not sure yet"]
        opts = ['<option value="">Choose a session type</option>']
        for label in labels:
            sel = " selected" if label == selected else ""
            opts.append(f'<option value="{_esc(label)}"{sel}>{_esc(label)}</option>')
        return "".join(opts)

    def lead_form(self, *, uid: str, studio: dict | None, path: str, heading: str, intro: str,
                  with_city: bool = False, preselect: str = "") -> str:
        """Render the Book Now form. studio=None means the homepage / general form."""
        studio_fields = ""
        if studio is not None:
            studio_fields = (f'<input type="hidden" name="studio_name" value="{_esc(studio["name"])}">'
                             f'<input type="hidden" name="studio_slug" value="{_esc(studio["slug"])}">'
                             f'<input type="hidden" name="city" value="{_esc(studio["city"])}">')
        city_field = ""
        if with_city:
            opts = '<option value="">Choose a Texas city</option>' + "".join(
                f'<option value="{_esc(c.name)}">{_esc(c.name)}</option>' for c in self.by_name)
            city_field = (f'<div class="lead-field"><label for="{uid}-city">City</label>'
                          f'<select id="{uid}-city" name="city" required>{opts}</select></div>')
        page_key = "studio" if studio is not None else "home"
        return f"""<section class="section-block lead-block" id="book">
  <h2>{_esc(heading)}</h2>
  <p class="muted">{_esc(intro)}</p>
  <form class="form-card lead-form" action="/api/lead/" method="post" data-lead-form>
    <input type="hidden" name="page" value="{page_key}">
    <input type="hidden" name="page_url" value="{_esc(self.abs_url(path))}">
    {studio_fields}
    <div class="lead-row">
      <div class="lead-field"><label for="{uid}-name">Your name</label><input id="{uid}-name" name="name" type="text" autocomplete="name" required maxlength="120"></div>
      <div class="lead-field"><label for="{uid}-email">Email</label><input id="{uid}-email" name="email" type="email" autocomplete="email" required maxlength="200"></div>
    </div>
    <div class="lead-row">
      <div class="lead-field"><label for="{uid}-phone">Phone <span class="muted">(optional)</span></label><input id="{uid}-phone" name="phone" type="tel" autocomplete="tel" maxlength="40"></div>
      <div class="lead-field"><label for="{uid}-date">Preferred date <span class="muted">(optional)</span></label><input id="{uid}-date" name="preferred_date" type="date" data-min-today></div>
    </div>
    <div class="lead-row">
      {city_field}
      <div class="lead-field"><label for="{uid}-service">Session type</label><select id="{uid}-service" name="service" required>{self.lead_service_options(preselect)}</select></div>
    </div>
    <label for="{uid}-message">Tell us about your session <span class="muted">(optional)</span></label>
    <textarea id="{uid}-message" name="message" maxlength="3000" placeholder="Group size, location, what you have in mind"></textarea>
    <div class="hp" aria-hidden="true"><label for="{uid}-website">Leave this empty</label><input id="{uid}-website" name="website_url" type="text" tabindex="-1" autocomplete="off"></div>
    <button class="btn btn-orange" type="submit">{CTA_LABEL}</button>
    <p class="note">We pass your request along and the studio follows up by email or phone. See our <a href="/privacy/">Privacy Policy</a>.</p>
    <p class="form-status" role="status" aria-live="polite"></p>
  </form>
</section>"""

    def studio_lead_section(self, studio: dict, city) -> str:
        category = self.studio_primary_category_label(studio)
        return self.lead_form(
            uid="lead", studio=studio, path=studio["url_path"],
            heading=f"Book {studio['name']}",
            intro=f"Send one request and {studio['name']} in {city.name}, Texas can get back to you about your session.",
            preselect=category)

    def studio_primary_category_label(self, studio: dict) -> str:
        self.prepare_categories()
        for c in self.categories:
            if c["id"] in self.cat_ev.get(studio["place_id"], {}):
                return c["label"]
        return ""

    def home_lead_section(self) -> str:
        form = self.lead_form(
            uid="home-lead", studio=None, path="/", heading="Book a Texas photo studio",
            intro="Tell us the city and the kind of session. We send your request to a photo studio that fits.",
            with_city=True)
        return f'<section class="section section-sand"><div class="wrap lead-wrap">{form}</div></section>'

    def card_cta(self) -> str:
        return f'<span class="btn btn-orange card-book" data-book>{CTA_LABEL}</span>'
