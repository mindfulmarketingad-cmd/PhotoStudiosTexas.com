"""Legal pages, the claim/removal form page, the thank-you page, and the order form.

Mixed into build.Site. Stdlib only. Wording is plain-language policy text for the
photo editing services and the directory; it is not a substitute for legal advice.
"""

from __future__ import annotations

from pathlib import Path

from directory_pages import esc

ROOT = Path(__file__).resolve().parents[1]

EFFECTIVE = "November 26, 2026"
OWNER = "David Ferebee"
BIZ = "Photo Studios Texas"

LEGAL_LINKS = [
    ("/privacy/", "Privacy Policy"),
    ("/terms/", "Terms of Service"),
    ("/refund-policy/", "Refund Policy"),
    ("/disclaimer/", "Directory Disclaimer"),
]

UPLOAD_ACCEPT = ".jpg,.jpeg,.png,.webp,.gif,.heic,.heif,.tif,.tiff,.bmp,.avif,.dng,.psd,.zip,image/*"


class TrustMixin:
    # ---------- shared pieces ----------
    def legal_links_html(self) -> str:
        return " · ".join(f'<a href="{href}">{label}</a>' for href, label in LEGAL_LINKS)

    def claim_href(self, studio_name: str = "", url_path: str = "", removal: bool = False) -> str:
        from urllib.parse import quote
        query = []
        if studio_name:
            query.append("studio=" + quote(studio_name, safe=""))
        if url_path:
            query.append("url=" + quote(url_path, safe=""))
        if removal:
            query.append("type=removal")
        return "/claim-listing/" + ("?" + "&".join(query) if query else "")

    def order_form(self, service: dict | None, subject: str, submit_label: str) -> str:
        options = []
        if service is None:
            options.append('<option value="">General question</option>')
        for item in self.services:
            selected = " selected" if service and item["slug"] == service["slug"] else ""
            options.append(f'<option value="{esc(item["slug"])}"{selected}>{esc(item["name"])}</option>')
        required = " required" if service is not None else ""
        placeholder = "What should change in the photos?"
        if service and service.get("formPlaceholder"):
            placeholder = service["formPlaceholder"]
        placeholder = placeholder.replace("Paste a share link to your original photo and tell us", "Tell us")
        kind = "order" if service is not None else "contact"
        upload = ""
        if service is not None:
            upload = f"""
  <label for="order-files">Your photos <span class="muted">(optional)</span></label>
  <input id="order-files" name="photos" type="file" multiple accept="{UPLOAD_ACCEPT}">
  <p class="note">Upload up to 12 files, 25 MB each (JPG, PNG, WebP, HEIC, TIFF, PSD or a ZIP). You can also paste a share link in the instructions. Files are sent securely and used only for your order.</p>
  <ul class="file-list" id="order-file-list" aria-live="polite"></ul>"""
        terms = ""
        if service is not None:
            terms = '<p class="note">By sending an order you agree to the <a href="/terms/">Terms</a>, <a href="/refund-policy/">Refund Policy</a> and <a href="/privacy/">Privacy Policy</a>.</p>'
        return f"""<form id="order-form" class="form-card" action="/api/submit" method="post" data-pst-form data-subject="{esc(subject)}" data-has-files="{'1' if service is not None else '0'}">
  <input type="hidden" name="kind" value="{kind}">
  <input type="hidden" name="page" value="">
  <label for="order-service">Service</label>
  <select id="order-service" name="service"{required}>{"".join(options)}</select>
  <label for="order-name">Name</label>
  <input id="order-name" name="name" type="text" autocomplete="name" required maxlength="120">
  <label for="order-email">Email</label>
  <input id="order-email" name="email" type="email" autocomplete="email" required maxlength="200">
  <label for="order-instructions">Instructions</label>
  <textarea id="order-instructions" name="message" required maxlength="5000" placeholder="{esc(placeholder)}"></textarea>{upload}
  <div class="hp" aria-hidden="true"><label for="order-website">Leave this empty</label><input id="order-website" name="website_url" type="text" tabindex="-1" autocomplete="off"></div>
  {terms}
  <button class="btn" type="submit">{esc(submit_label)}</button>
  <p class="form-status" role="status" aria-live="polite"></p>
</form>"""

    # ---------- pages ----------
    def _legal_page(self, path: str, title: str, description: str, heading: str, inner: str, extra_crumb: str | None = None) -> None:
        crumbs = [("Home", "/"), (heading, None)]
        others = " · ".join(f'<a href="{h}">{l}</a>' for h, l in LEGAL_LINKS if h != path)
        body = f"""<div class="wrap page-head legal-page">
  {self.crumbs(crumbs)}
  <h1>{esc(heading)}</h1>
  <hr class="rule">
  <p class="muted">{BIZ} · Effective {EFFECTIVE}</p>
  {inner}
  <hr class="rule">
  <p class="note">Also see: {others}. Questions? Use the <a href="/about/#contact">contact form</a>.</p>
</div>"""
        self.write_page(path, self.layout(title, description, path, body, "", [self.breadcrumb_schema(crumbs, path)]))

    def build_legal(self) -> None:
        svc = {s["slug"]: s for s in self.services}
        edit = svc.get("photo-editing", {})
        enh = svc.get("photo-enhancement", {})
        edit_days = edit.get("delivery", "4-day delivery")
        enh_days = enh.get("delivery", "3-day delivery")
        edit_rev = edit.get("revisions", "3 revisions")
        enh_rev = enh.get("revisions", "1 revision")

        self._legal_page("/privacy/", "Privacy Policy | PhotoStudiosTexas.com",
            "How PhotoStudiosTexas.com handles information from forms, photo uploads, payments, and analytics, and what we do not collect.",
            "Privacy Policy", f"""
  <p class="lede">{BIZ} ("we", "us") operates PhotoStudiosTexas.com, a directory of Texas photo studios with photo editing and enhancement services and free photo tools. The site is owned by {OWNER}. This page explains what we collect and why.</p>
  <h2>What we collect</h2>
  <ul class="plain-list">
    <li><strong>Forms.</strong> When you send an order, contact message, listing claim or removal request, we receive the name, email address, message and any other details you type, plus the page you sent it from.</li>
    <li><strong>Photos you upload.</strong> Files you attach to an order are uploaded to our secure file storage so we can edit them. We use them only to complete your order.</li>
    <li><strong>Payments.</strong> Payments are processed by Stripe on Stripe's checkout page. We never see or store your card number; Stripe gives us your name, email and order details.</li>
    <li><strong>Approximate location.</strong> To show studios near you on the homepage, our host reads an approximate city from your IP address for that page view. We do not store it. If you tap "use my precise location", your browser shares coordinates with the page only to sort studios on your device; they are not sent to us.</li>
    <li><strong>Analytics.</strong> We use Vercel Web Analytics to count page views and referrers. It does not use cookies and does not track you across sites.</li>
  </ul>
  <h2>How we use it</h2>
  <p>To reply to you, deliver and support orders, process corrections to directory listings, keep the site secure, and understand which pages are useful. We do not sell your information or use it for advertising profiles.</p>
  <h2>Who we share it with</h2>
  <ul class="plain-list">
    <li><strong>Editors.</strong> The people who work on your photos receive the files and instructions for your order, and are expected to keep them private and delete them when the order is done.</li>
    <li><strong>Service providers.</strong> Our hosting (Vercel), file storage (Vercel Blob), email delivery (Resend) and payment processor (Stripe) handle data on our behalf.</li>
    <li><strong>Legal.</strong> We may disclose information if the law requires it.</li>
  </ul>
  <h2>Free photo tools</h2>
  <p>The tools under <a href="/tools/">Free Tools</a> run in your browser. Photos you open in them are not uploaded to our servers.</p>
  <h2>How long we keep it</h2>
  <p>Uploaded photos and finished files are deleted within 90 days after your order is complete, or sooner if you ask. Order and contact emails are kept as long as needed for support, tax and dispute records.</p>
  <h2>Directory listings</h2>
  <p>Business listings are public business information gathered from Google Maps. See the <a href="/disclaimer/">Directory Disclaimer</a>. Owners can <a href="{self.claim_href()}">update a listing</a> or <a href="{self.claim_href(removal=True)}">request removal</a>.</p>
  <h2>Your choices</h2>
  <p>You can ask to see, correct or delete the information we hold about you by using the <a href="/about/#contact">contact form</a>. Residents of some states have additional rights to access and delete personal information; we honor those requests. The site is not directed at children under 13.</p>
  <h2>Changes</h2>
  <p>If we change this policy we will update the date above.</p>
""")

        self._legal_page("/terms/", "Terms of Service | PhotoStudiosTexas.com",
            "Terms for using PhotoStudiosTexas.com, ordering photo editing or enhancement services, and the free photo tools.",
            "Terms of Service", f"""
  <p class="lede">By using PhotoStudiosTexas.com or ordering a service, you agree to these terms. The site is operated by {BIZ}, owned by {OWNER}.</p>
  <h2>The directory</h2>
  <p>The directory is information only. Listings come from public sources, may be out of date, and are not endorsements. Rankings and guides are based on the public ratings described on each page, and nobody pays for placement. See the <a href="/disclaimer/">Directory Disclaimer</a>. Confirm hours, prices and availability with a studio before you visit.</p>
  <h2>Photo services</h2>
  <ul class="plain-list">
    <li><strong>What you get.</strong> The package, price, delivery time and revisions shown on each <a href="/services/">service page</a> at the time you order. Current packages: <a href="/services/photo-editing/">Photo Editing &amp; Retouching</a> ({esc(edit_days)}, {esc(edit_rev)}) and <a href="/services/photo-enhancement/">Photo Enhancement &amp; Upscaling</a> ({esc(enh_days)}, {esc(enh_rev)}).</li>
    <li><strong>Delivery time</strong> starts when we have your payment and photos usable for the work. Delivery is a digital file; we do not ship prints.</li>
    <li><strong>Your photos.</strong> You promise you own the photos or have permission to edit them, and that they do not include illegal content or content that infringes anyone's rights. We may decline or cancel an order for content we won't work on and refund it in full.</li>
    <li><strong>Ownership.</strong> You keep the rights to your photos and to the finished files. You allow us and the editors working on your order to use them only to do the work.</li>
    <li><strong>Results.</strong> Editing is a creative service. We work from your instructions, but we cannot guarantee a result for badly damaged or very low-detail images. See the <a href="/refund-policy/">Refund Policy</a>.</li>
    <li><strong>Payment.</strong> Prices are in US dollars and paid through Stripe.</li>
  </ul>
  <h2>Free tools</h2>
  <p>The photo tools are provided free, as is. They run in your browser, and you are responsible for the files you process.</p>
  <h2>Using the site</h2>
  <p>Do not scrape the site at a rate that harms it, attempt to break or probe it, or use it to send spam. We may block abusive traffic.</p>
  <h2>No warranty and limits of liability</h2>
  <p>The site, directory data and free tools are provided "as is" without warranties of any kind. To the fullest extent the law allows, our total liability for any claim relating to the site or a service is limited to the amount you paid for that service, and we are not liable for indirect or consequential losses.</p>
  <h2>Changes and contact</h2>
  <p>We may update these terms; the date above shows the latest version. These terms are governed by the laws of the State of Georgia, USA. Contact us through the <a href="/about/#contact">contact form</a>.</p>
""")

        self._legal_page("/refund-policy/", "Refund Policy | PhotoStudiosTexas.com",
            "Refund and revision policy for photo editing and enhancement orders: turnaround, revisions, late or undelivered orders, and how to ask.",
            "Refund Policy", f"""
  <p class="lede">We want you to be happy with your photos. This policy covers the paid services on PhotoStudiosTexas.com. The directory and tools are free.</p>
  <h2>Turnaround</h2>
  <ul class="plain-list">
    <li><a href="/services/photo-editing/">Photo Editing &amp; Retouching</a>: {esc(edit_days)}.</li>
    <li><a href="/services/photo-enhancement/">Photo Enhancement &amp; Upscaling</a>: {esc(enh_days)}.</li>
  </ul>
  <p>The clock starts when payment is received and we have your photos and instructions. If we need more information from you, the clock pauses until you reply.</p>
  <h2>Revisions</h2>
  <p>Each order includes the revisions listed on the service page ({esc(edit_rev)} for editing, {esc(enh_rev)} for enhancement). Reply to the delivery email with what you'd like changed. Revisions are for adjusting the work you ordered, not for new tasks.</p>
  <h2>When you get a refund</h2>
  <ul class="plain-list">
    <li><strong>Not delivered.</strong> If we have not delivered within 3 days after the quoted turnaround, you can ask for a full refund, or keep waiting.</li>
    <li><strong>Can't be done.</strong> If we can't do the work you asked for (for example, a face is too blurred to restore accurately), we'll tell you and refund the order in full.</li>
    <li><strong>Doesn't match your order.</strong> If the result doesn't match your written instructions after your included revisions, tell us within 14 days of delivery. We will refund in full or in part, depending on how far the work missed the instructions.</li>
    <li><strong>Charged in error</strong> or charged twice: we refund the extra charge.</li>
  </ul>
  <h2>When we can't refund</h2>
  <p>Once you have accepted a delivery, or 14 days after delivery, the order is final. We can't refund for a change of mind, or for new instructions that weren't in your original order, though we are happy to quote a new order.</p>
  <h2>How to ask</h2>
  <p>Use the <a href="/about/#contact">contact form</a> with your name, the email you ordered with, and what went wrong. We aim to reply within 2 business days. Approved refunds go back to your original payment method through Stripe, and usually appear within 5 to 10 business days.</p>
""")

        self._legal_page("/disclaimer/", "Directory Disclaimer | PhotoStudiosTexas.com",
            "Where PhotoStudiosTexas.com listing data comes from, that it is not affiliated with Google or the studios listed, and how owners can correct or remove a listing.",
            "Directory Disclaimer", f"""
  <p class="lede">PhotoStudiosTexas.com is an independent directory. It is not owned by, affiliated with, or endorsed by Google or by any studio listed.</p>
  <h2>Where listing data comes from</h2>
  <p>Business names, addresses, phone numbers, websites, hours, categories, ratings and review counts come from public Google Maps information, with some details matched from each studio's own public website. Ratings and review counts belong to Google's reviewers; we show only the summary figures and link to the full reviews on Google.</p>
  <h2>Accuracy</h2>
  <p>Businesses change hours, move and close. The data is a snapshot and may be out of date or wrong. We make no guarantee that a listing is complete or current. Please confirm with the studio before you visit or book.</p>
  <h2>No endorsement, no paid placement</h2>
  <p>A listing is not a recommendation. Studios do not pay to be listed or ranked. Trademarks, names and logos belong to their owners and are used only to identify the business.</p>
  <h2>Own or manage a studio?</h2>
  <p><a href="{self.claim_href()}">Claim or update your listing</a>, or <a href="{self.claim_href(removal=True)}">request removal</a>. We review requests and reply by email. Updating your Google Business Profile also fixes the next refresh of our data.</p>
""")

    def build_claim_pages(self) -> None:
        crumbs = [("Home", "/"), ("Claim or update a listing", None)]
        path = "/claim-listing/"
        body = f"""<div class="wrap page-head">
  {self.crumbs(crumbs)}
  <h1>Claim, update or remove a listing</h1>
  <hr class="rule">
  <p class="lede">Own or manage a photo studio in this directory? Tell us what to fix, or ask us to take the listing down. We reply by email, usually within 2 business days.</p>
  <div class="split">
    <form id="claim-form" class="form-card" action="/api/submit" method="post" data-pst-form data-has-files="0" data-subject="Listing request">
      <input type="hidden" name="kind" value="claim">
      <input type="hidden" name="page" value="">
      <label for="claim-request">What do you need?</label>
      <select id="claim-request" name="request">
        <option value="Claim this listing">Claim this listing</option>
        <option value="Update listing details">Update listing details</option>
        <option value="Remove this listing">Remove this listing</option>
      </select>
      <label for="claim-studio">Studio name</label>
      <input id="claim-studio" name="studio_name" type="text" required maxlength="200">
      <label for="claim-url">Listing page on this site</label>
      <input id="claim-url" name="studio_url" type="text" maxlength="400" placeholder="https://…/tx/city/studio/">
      <label for="claim-name">Your name</label>
      <input id="claim-name" name="name" type="text" autocomplete="name" required maxlength="120">
      <label for="claim-email">Your email</label>
      <input id="claim-email" name="email" type="email" autocomplete="email" required maxlength="200">
      <label for="claim-role">Your role</label>
      <select id="claim-role" name="role"><option>Owner</option><option>Manager</option><option>Employee</option><option>Other</option></select>
      <label for="claim-website">Studio website <span class="muted">(helps us verify you)</span></label>
      <input id="claim-website" name="website" type="url" maxlength="300" placeholder="https://">
      <label for="claim-message">Details</label>
      <textarea id="claim-message" name="message" required maxlength="5000" placeholder="What should change (hours, phone, services, website), or why the listing should be removed?"></textarea>
      <div class="hp" aria-hidden="true"><label for="claim-hp">Leave this empty</label><input id="claim-hp" name="website_url" type="text" tabindex="-1" autocomplete="off"></div>
      <button class="btn" type="submit">Send request</button>
      <p class="form-status" role="status" aria-live="polite"></p>
    </form>
    <aside class="panel">
      <h2>What happens next</h2>
      <ol class="plain-list">
        <li>We email you from the address you give, to confirm you speak for the studio.</li>
        <li>We update or remove the listing. Removals are made as soon as we confirm the request.</li>
        <li>Your Google Business Profile also feeds our data, so keeping it current keeps this page current.</li>
      </ol>
      <p class="note">See the <a href="/disclaimer/">Directory Disclaimer</a> and <a href="/privacy/">Privacy Policy</a>. <a href="/cities/">Find your studio</a>.</p>
    </aside>
  </div>
</div>"""
        doc = self.layout("Claim, Update or Remove a Listing | PhotoStudiosTexas.com",
                          "Studio owners: claim or update your photo studio listing, or ask for it to be removed from PhotoStudiosTexas.com.",
                          path, body, "", [], robots="noindex,follow")
        self._write_unlisted(path, doc)

        thanks_path = "/thanks/"
        thanks = """<div class="wrap page-head">
  <h1 id="thanks-title">Thank you. We got your message.</h1>
  <hr class="rule">
  <p id="thanks-ok">We'll reply by email, usually within 2 business days. Orders start once payment and your photos are in.</p>
  <p id="thanks-err" hidden>Something went wrong sending your message. Please go back and try again.</p>
  <p><a class="btn" href="/">Back to the directory</a> <a class="btn btn-small" href="/services/">Photo services</a></p>
</div>
<script>if(/[?&]error=1/.test(location.search)){document.getElementById('thanks-title').textContent='We could not send that';document.getElementById('thanks-ok').hidden=true;document.getElementById('thanks-err').hidden=false;}</script>"""
        self._write_unlisted(thanks_path, self.layout("Thank you | PhotoStudiosTexas.com",
                          "Thanks for contacting PhotoStudiosTexas.com.", thanks_path, thanks, "", [], robots="noindex,follow"))

    def _write_unlisted(self, path: str, document: str) -> None:
        target = ROOT / "dist" / path.strip("/") / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(document, encoding="utf-8")
