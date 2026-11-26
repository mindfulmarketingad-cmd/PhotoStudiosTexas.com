// Returns the visitor's approximate location from Vercel's IP geolocation headers.
// No IP address is logged or returned. Used by /assets/home-geo.js.
module.exports = function handler(req, res) {
  const h = req.headers;
  const decode = (v) => {
    if (!v) return null;
    try { return decodeURIComponent(String(v)); } catch (e) { return String(v); }
  };
  const body = {
    city: decode(h["x-vercel-ip-city"]),
    region: decode(h["x-vercel-ip-country-region"]),
    country: decode(h["x-vercel-ip-country"]),
    latitude: h["x-vercel-ip-latitude"] ? Number(h["x-vercel-ip-latitude"]) : null,
    longitude: h["x-vercel-ip-longitude"] ? Number(h["x-vercel-ip-longitude"]) : null,
  };
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "private, no-store");
  res.statusCode = 200;
  res.end(JSON.stringify(body));
};
