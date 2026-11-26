// Receives order, contact, listing-claim and removal-request forms and emails them to the
// site owner through Resend. The recipient is fixed server-side (FORM_TO_EMAIL), so this
// endpoint cannot be used to send mail to anyone else.
const TO = process.env.FORM_TO_EMAIL || "mindfulmarketingad@gmail.com";
const FROM = process.env.FORM_FROM_EMAIL || "Photo Studios Texas <forms@accessbell.co>";

const KINDS = {
  order: "Order",
  contact: "Contact",
  claim: "Listing claim / update",
  removal: "Listing removal request",
};

function esc(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function clean(value, max) {
  return String(value == null ? "" : value).replace(/\r\n/g, "\n").trim().slice(0, max);
}

function wantsJson(req) {
  return (req.headers.accept || "").includes("application/json")
    || (req.headers["content-type"] || "").includes("application/json");
}

function reply(req, res, status, payload, redirect) {
  if (wantsJson(req)) {
    res.statusCode = status;
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    return res.end(JSON.stringify(payload));
  }
  res.statusCode = 303;
  res.setHeader("Location", redirect || (status === 200 ? "/thanks/" : "/thanks/?error=1"));
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

function isBlobUrl(url) {
  try {
    const u = new URL(url);
    return u.protocol === "https:" && /\.blob\.vercel-storage\.com$/.test(u.hostname);
  } catch (e) {
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
  if (clean(body.website_url, 200)) {
    return reply(req, res, 200, { ok: true });
  }

  const kind = KINDS[body.kind] ? body.kind : "contact";
  const name = clean(body.name, 120);
  const email = clean(body.email, 200);
  const message = clean(body.message || body.instructions, 5000);
  if (!name || !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email) || !message) {
    return reply(req, res, 400, { ok: false, error: "Please fill in your name, a valid email, and a message." }, "/thanks/?error=1");
  }

  const fields = [
    ["Type", KINDS[kind]],
    ["Name", name],
    ["Email", email],
  ];
  const extra = {
    service: "Service", studio_name: "Studio", studio_url: "Studio page", request: "Request",
    role: "Role", website: "Studio website", phone: "Phone", page: "Submitted from",
  };
  for (const key of Object.keys(extra)) {
    const v = clean(body[key], 400);
    if (v) fields.push([extra[key], v]);
  }

  let files = body.files || [];
  if (typeof files === "string") {
    try { files = JSON.parse(files); } catch (e) { files = []; }
  }
  if (!Array.isArray(files)) files = [];
  files = files.slice(0, 12).map((f) => ({
    url: clean(f && f.url, 600),
    name: clean(f && f.name, 160) || "photo",
    size: Number(f && f.size) || 0,
  })).filter((f) => isBlobUrl(f.url));

  const subject = `[PhotoStudiosTexas] ${KINDS[kind]}: ${clean(body.service || body.studio_name || name, 80)}`;
  const text = fields.map(([k, v]) => `${k}: ${v}`).join("\n")
    + `\n\nMessage:\n${message}`
    + (files.length ? `\n\nPhotos (${files.length}):\n` + files.map((f) => `${f.name}${f.size ? " (" + Math.round(f.size / 1024) + " KB)" : ""}: ${f.url}`).join("\n") : "");
  const html = `<div style="font:15px/1.5 -apple-system,Segoe UI,Arial,sans-serif;color:#111">`
    + `<h2 style="margin:0 0 12px;color:#e8590c">${esc(KINDS[kind])}</h2>`
    + `<table cellpadding="4" style="border-collapse:collapse">`
    + fields.map(([k, v]) => `<tr><td style="color:#666;vertical-align:top">${esc(k)}</td><td><strong>${esc(v)}</strong></td></tr>`).join("")
    + `</table><p style="white-space:pre-wrap;border-left:3px solid #e8590c;padding-left:12px;margin:16px 0">${esc(message)}</p>`
    + (files.length ? `<p><strong>Photos (${files.length})</strong></p><ul>` + files.map((f) => `<li><a href="${esc(f.url)}">${esc(f.name)}</a>${f.size ? " (" + Math.round(f.size / 1024) + " KB)" : ""}</li>`).join("") + `</ul>` : "")
    + `<p style="color:#888;font-size:12px">Reply to this email to answer the customer directly.</p></div>`;

  const key = process.env.RESEND_API_KEY;
  if (!key) {
    console.error("RESEND_API_KEY is not set");
    return reply(req, res, 500, { ok: false, error: "Sending is not configured yet." });
  }
  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({ from: FROM, to: [TO], reply_to: email, subject, text, html }),
    });
    if (!r.ok) {
      console.error("Resend error", r.status, await r.text());
      return reply(req, res, 502, { ok: false, error: "We could not send your message. Please try again in a minute." });
    }
  } catch (e) {
    console.error("Resend fetch failed", e);
    return reply(req, res, 502, { ok: false, error: "We could not send your message. Please try again in a minute." });
  }
  return reply(req, res, 200, { ok: true });
};
