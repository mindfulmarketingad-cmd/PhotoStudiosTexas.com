// Issues short-lived client upload tokens so customers can send photos straight to
// Vercel Blob (bypassing the 4.5 MB function body limit). Images only, 25 MB each.
const MAX_BYTES = 25 * 1024 * 1024;
const ALLOWED = [
  "image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif",
  "image/tiff", "image/bmp", "image/avif", "image/x-adobe-dng", "image/vnd.adobe.photoshop",
  "application/zip",
];

function allowedOrigin(req) {
  const origin = req.headers.origin || "";
  if (!origin) return false;
  try {
    const host = new URL(origin).hostname;
    return host === "photostudiostexas.com" || host.endsWith(".photostudiostexas.com")
      || host === "photostudiostexas.vercel.app" || host === "localhost"
      || (host.startsWith("photostudiostexas-") && host.endsWith(".vercel.app"));
  } catch (e) {
    return false;
  }
}

async function readJson(req) {
  if (req.body && typeof req.body === "object") return req.body;
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString("utf8") || "{}");
}

module.exports = async function handler(req, res) {
  res.setHeader("Cache-Control", "no-store");
  if (req.method !== "POST") {
    res.statusCode = 405;
    res.setHeader("Allow", "POST");
    return res.end(JSON.stringify({ error: "Method not allowed" }));
  }
  if (!allowedOrigin(req)) {
    res.statusCode = 403;
    return res.end(JSON.stringify({ error: "Forbidden" }));
  }
  try {
    const { handleUpload } = await import("@vercel/blob/client");
    const body = await readJson(req);
    const json = await handleUpload({
      body,
      request: req,
      onBeforeGenerateToken: async (pathname) => {
        if (!/^orders\/[A-Za-z0-9._\- ()]{1,150}$/.test(pathname)) {
          throw new Error("Invalid file name");
        }
        return {
          allowedContentTypes: ALLOWED,
          maximumSizeInBytes: MAX_BYTES,
          addRandomSuffix: true,
        };
      },
      onUploadCompleted: async () => {},
    });
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.statusCode = 200;
    res.end(JSON.stringify(json));
  } catch (err) {
    res.setHeader("Content-Type", "application/json; charset=utf-8");
    res.statusCode = 400;
    res.end(JSON.stringify({ error: String((err && err.message) || err) }));
  }
};
