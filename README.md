# PhotoStudiosTexas.com

Static directory of photo studios in Texas, plus a photo editing service. Pages are plain HTML generated from a cleaned Outscraper export. [Vercel](https://vercel.com) builds the site with `python3 scripts/build.py` and serves `dist/`. The canonical base URL is `https://www.photostudiostexas.com` (attach the domain in Vercel when you are ready; no template change is required).

## Page counts from this export

| | |
| --- | --- |
| Source rows | 2,006 |
| Studios published | 1,860 |
| City hubs | 324 |
| Cities with a single studio | 147 |
| Indexable HTML pages | 2,191 |
| Temporarily closed (kept and labeled) | 88 |

The link checker reaches every indexable page within 2 clicks of the home page.

### Largest cities

Houston 284, Dallas 152, Austin 123, San Antonio 93, Fort Worth 64, El Paso 45, McKinney 29, Arlington 26, Katy 26, McAllen 24, Spring 24, Plano 22.

## URLs

| Path | Page |
| --- | --- |
| `/` | Texas home: search, featured studios, every city |
| `/tx/` | Texas hub used in breadcrumbs |
| `/tx/<city>/` | City hub: every studio, nearby cities, editing CTA |
| `/tx/<city>/<studio>/` | Studio details, other studios in the city, nearby cities |
| `/cities/` | A–Z city index |
| `/services/` | Service list (add more here later) |
| `/services/photo-editing/` | Professional Photo Editing & Retouching, $39.88, with a before-and-after gallery |
| `/about/` | About and contact |
| `/sitemap/` | HTML sitemap |
| `/sitemap.xml` | XML sitemap |
| `/robots.txt` | Robots file |

City hubs link to every studio in that city, to nearby cities (by the average coordinates of listings in each city), back to `/` and `/tx/`, and to the editing service. Studio pages use the breadcrumb Home → Texas → City → Studio, with `BreadcrumbList` schema. Studio pages include `LocalBusiness` schema. Titles, descriptions, and canonical tags are unique.

## Set the payment link

Edit **`config/site.json`**. This is the only place the payment URL is defined:

```json
"STRIPE_PAYMENT_LINK": "https://buy.stripe.com/your-link"
```

Leave it as `""` until the Stripe Payment Link exists. A value that starts with `https://` becomes the **Order Now - $39.88** button. Anything else keeps the button on the order form.

Also in that file:

- `ORDER_FORM_ENDPOINT` — optional `https://` URL that receives the order form as a normal POST (`name`, `email`, `instructions`, and `service`). Leave empty to open a `mailto:` to `CONTACT_EMAIL`.
- `CONTACT_EMAIL` — address used for the mailto fallback. The form does not upload files; the page asks the customer to paste a share link or attach images in their email app.

Rebuild after changing the file:

```bash
python3 scripts/build.py
```

That regenerates `dist/assets/site-config.js` from the same keys. To add another service later, append an object to `config/services.json` and rebuild. The nav item stays on photo editing; `/services/` lists every entry.

## Rebuild from a new Outscraper export

The cleaner needs `openpyxl` (`pip install -r requirements.txt`). The site build itself is Python standard library only, which is what Vercel runs.

```bash
python3 scripts/clean_data.py path/to/new-export.xlsx
python3 scripts/build.py
python3 scripts/check_links.py
python3 -m http.server 4173 --directory dist
```

With no path, `clean_data.py` reads `data/source/outscraper-photography-studio-tx.xlsx`. Cleaning writes `data/studios.json` and `data/cleaning-report.json`. Do not hand-edit studio fields; the generator prints only what is in that file.

`scripts/check_links.py` fails on broken internal links, orphan HTML pages, a sitemap that does not match the pages, duplicate titles, missing favicon or logo tags, or the word “Fiverr”.

## How the export was cleaned

Nothing was filled in when the export left a field blank. Decisions recorded in `data/cleaning-report.json`:

- Kept `state_code` TX only. Dropped 60 rows in other states (the query also returned places such as Dallas, Georgia, and New York).
- Dropped 84 Texas rows with `business_status` `CLOSED_PERMANENTLY`. Kept 88 `CLOSED_TEMPORARILY` rows and labeled them.
- Did not fold small cities into a neighbor. Every studio stays on the city named in the listing, including the 147 cities with one studio. Nearby-city links are the grouping.
- City strings are kept as published, except whitespace cleanup and a short alias list: `St Jo` → Saint Jo, `Mt Pleasant` → Mount Pleasant (plus Fort Worth, DeSoto, McKinney, and McAllen variants for later exports).
- Removed 2 duplicate listings that share a normalized name, city, and street address: a second The Evergreen Studios row in Houston (kept the one with 11 reviews) and a Willow Haus row in Mineral Wells whose address was garbled. Same-name studios at different addresses stay, including chains.
- Category on the page is the export’s `type` field. `subtypes` are kept separately. The export’s `category` column was empty for almost every row. Descriptions, ratings, hours, phones, websites, and photo URLs are copied only when present.

## Logo and icons

`assets/brand/` holds the mark (aperture plus a Texas star) and the PhotoStudios / Texas wordmark:

- `logo-light.svg` — white wordmark for the black header
- `logo-dark.svg` — black wordmark for the white footer
- `favicon.svg`, `favicon.ico` (16 and 32), `apple-touch-icon.png` (180), `icon-192.png`, `icon-512.png`
- `og-image.png` (1200×630) and `site.webmanifest`

Every page links these from `<head>`. Regenerate them locally (not on Vercel) with Pillow, fontTools, and CairoSVG:

```bash
pip install pillow fonttools cairosvg
python3 scripts/render_brand.py
```

## Layout

```
config/site.json          payment link, contact email, feature counts
config/services.json      service packages
data/studios.json         cleaned listings
data/cleaning-report.json what was dropped and why
data/source/              original xlsx
assets/site.css
assets/site.js            search, city jump, order button, mailto form
assets/brand/             logo, favicons, manifest, social image
scripts/clean_data.py
scripts/build.py
scripts/check_links.py
scripts/render_brand.py
vercel.json               build command and dist output
```

`dist/` is gitignored. Vercel creates it on deploy.
