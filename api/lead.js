// "Book Now" lead form (studio pages, homepage). Stores each lead in the shared general
// leads table in Supabase (same `leads` table lakelandconcretecontractors.org writes to,
// tagged with page_url = photostudiostexas.com) and also emails David through Resend.
//
// Env (Vercel): LEADS_SUPABASE_SERVICE_ROLE_KEY  (service role key of the leads project; server only)
//               LEADS_SUPABASE_URL               (optional; defaults to the shared leads project)
//               RESEND_API_KEY, FORM_FROM_EMAIL, FORM_TO_EMAIL (already set for /api/submit)
// Keys are never committed or sent to the browser.
const SUPABASE_URL = (process.env.LEADS_SUPABASE_URL || "https://tbqigevoksabizjogvtm.supabase.co").replace(/\/+$/, "");
const SERVICE_KEY = process.env.LEADS_SUPABASE_SERVICE_ROLE_KEY || "";
const SITE_TAG = "photostudiostexas.com";
const TO = process.env.FORM_TO_EMAIL || "mindfulmarketingad@gmail.com";
const FROM = process.env.FORM_FROM_EMAIL || "Photo Studios Texas <forms@accessbell.co>";

function clean(value, max) {
  return String(value == null ? "" : value).replace(/\r\n/g, "\n").trim().slice(0, max);
}

function esc(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function wantsJson(req) {
  return (req.headers.accept || "").includes("application/json")
    || (req.headers["content-type"] || "").includes("application/json");
}

function reply(req, res, status, payload) {
  if (wantsJson(req)) {
    res.statusCode = status;
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    return res.end(JSON.stringify(payload));
  }
  res.statusCode = 303;
  res.setHeader("Location", status === 200 ? "/thanks/" : "/thanks/?error=1");
  return res.end();
}

async function parseBody(req) {
  if (req.body && typeof req.body === "object") return req.body;
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString("utf8");
  if ((req.headers["content-type"] || "").includes("application/json")) return JSON.parse(raw || "{}");
  return Object.fromEntries(new URLSearchParams(raw));
}

async function saveToSupabase(row) {
  if (!SERVICE_KEY) {
    console.error("LEADS_SUPABASE_SERVICE_ROLE_KEY is not set; lead was not stored in Supabase");
    return false;
  }
  try {
    const r = await fetch(`${SUPABASE_URL}/rest/v1/leads`, {
      method: "POST",
      headers: {
        apikey: SERVICE_KEY,
        Authorization: `Bearer ${SERVICE_KEY}`,
        "Content-Type": "application/json",
        Prefer: "return=minimal",
      },
      body: JSON.stringify(row),
    });
    if (!r.ok) {
      console.error("Supabase insert failed", r.status, await r.text());
      return false;
    }
    return true;
  } catch (e) {
    console.error("Supabase insert error", e);
    return false;
  }
}

async function sendEmail(subject, fields, message, replyTo) {
  const key = process.env.RESEND_API_KEY;
  if (!key) return false;
  const text = fields.map(([k, v]) => `${k}: ${v}`).join("\n") + (message ? `\n\nMessage:\n${message}` : "");
  const html = `<div style="font:15px/1.5 -apple-system,Segoe UI,Arial,sans-serif;color:#111">`
    + `<h2 style="margin:0 0 12px;color:#e8590c">New Book Now lead</h2><table cellpadding="4">`
    + fields.map(([k, v]) => `<tr><td style="color:#666;vertical-align:top">${esc(k)}</td><td><strong>${esc(v)}</strong></td></tr>`).join("")
    + `</table>${message ? `<p style="white-space:pre-wrap;border-left:3px solid #e8590c;padding-left:12px">${esc(message)}</p>` : ""}</div>`;
  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({ from: FROM, to: [TO], reply_to: replyTo, subject, text, html }),
    });
    if (!r.ok) console.error("Resend error", r.status, await r.text());
    return r.ok;
  } catch (e) {
    console.error("Resend fetch failed", e);
    return false;
  }
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") {
    res.statusCode = 405;
    res.setHeader("Allow", "POST");
    return res.end("Method not allowed");
  }
  let body;
  try {
    body = await parseBody(req);
  } catch (e) {
    return reply(req, res, 400, { ok: false, error: "Could not read the form." });
  }

  // Honeypot: real visitors leave this blank. Pretend success for bots.
  if (clean(body.website_url, 200)) return reply(req, res, 200, { ok: true });

  const name = clean(body.name, 120);
  const email = clean(body.email, 200);
  const phone = clean(body.phone, 40);
  const service = clean(body.service, 120);
  const date = clean(body.preferred_date, 40);
  const message = clean(body.message, 3000);
  const studioName = clean(body.studio_name, 200);
  const studioSlug = clean(body.studio_slug, 200);
  const city = clean(body.city, 120);
  const pageUrl = clean(body.page_url, 400);
  const pageKey = clean(body.page, 60) || (studioSlug ? "studio" : "home");
  const test = /^TEST\b/i.test(name) ? " (test)" : "";

  if (name.length < 2) return reply(req, res, 400, { ok: false, error: "Please enter your name." });
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email)) return reply(req, res, 400, { ok: false, error: "Please enter a valid email address." });
  if (phone && phone.replace(/\D/g, "").length < 7) return reply(req, res, 400, { ok: false, error: "That phone number looks too short." });
  if (date && !/^\d{4}-\d{2}-\d{2}$/.test(date)) return reply(req, res, 400, { ok: false, error: "Please pick a valid date." });

  const description = [
    studioName ? `Studio: ${studioName}${studioSlug ? ` (${studioSlug})` : ""}` : "Studio: any / not chosen",
    service ? `Service: ${service}` : "",
    date ? `Preferred date: ${date}` : "",
    city ? `City: ${city}` : "",
    pageUrl ? `Page: ${pageUrl}` : "",
    message ? `Message: ${message}` : "",
  ].filter(Boolean).join("\n");

  const row = {
    name,
    email,
    phone: phone || null,
    city: city || null,
    description,
    timeline: date || null,
    status: "new",
    page_url: SITE_TAG,
  };

  const stored = await saveToSupabase(row);
  const fields = [
    ["Source", `${SITE_TAG} / ${pageKey}`], ["Name", name], ["Email", email], ["Phone", phone],
    ["Studio", studioName], ["Service", service], ["City", city], ["Preferred date", date],
    ["Page", pageUrl], ["Saved to Supabase", stored ? "yes" : "NO - check LEADS_SUPABASE_SERVICE_ROLE_KEY"],
  ].filter(([, v]) => v);
  const emailed = await sendEmail(`[PhotoStudiosTexas] Book Now${test}: ${studioName || city || name}`, fields, message, email);

  if (!stored && !emailed) {
    return reply(req, res, 502, { ok: false, error: "We could not send your request. Please try again in a minute." });
  }
  return reply(req, res, 200, { ok: true, stored });
};
