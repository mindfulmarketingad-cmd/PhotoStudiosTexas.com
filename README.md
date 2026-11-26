# PhotoStudiosTexas.com

Static directory of photo studios in Texas, plus photo editing and photo enhancement services. Pages are plain HTML generated from a cleaned Outscraper export. [Vercel](https://vercel.com) builds the site with `python3 scripts/build.py` and serves `dist/`. The canonical base URL is `https://photostudiostexas.com`.

## Page counts from this export

| | |
| --- | --- |
| Source rows | 2,006 |
| Studios published | 1,860 |
| City hubs | 324 |
| Cities with a single studio | 147 |
| Indexable HTML pages | 2,192 |
| Temporarily closed (kept and labeled) | 88 |

The link checker reaches every indexable page within 2 clicks of the home page.

### Largest cities

Houston 284, Dallas 152, Austin 123, San Antonio 93, Fort Worth 64, El Paso 45, McKinney 29, Arlington 26, Katy 26, McAllen 24, Spring 24, Plano 22.

## URLs

| Path | Page |
| --- | --- |
| `/` | Texas home: full-width studio hero, city search, featured studios, every city |
| `/tx/` | Texas hub used in breadcrumbs |
| `/tx/<city>/` | City hub: every studio, nearby cities, editing CTA |
| `/tx/<city>/<studio>/` | Studio details, other studios in the city, nearby cities |
| `/cities/` | A–Z city index |
| `/services/` | Service hub listing photo editing and photo enhancement |
| `/services/photo-editing/` | Professional Photo Editing & Retouching, $39.88, with a before-and-after gallery |
| `/services/photo-enhancement/` | Photo Enhancement & Upscaling, $40 per photo |
| `/blog/` | Blog hub: ranked city guides |
| `/blog/best-photo-studios-in-<city>-tx/` | "The 10 Best Photo Studios in <City> Texas" for every city with 10+ studios (34 today). Ranking: `(reviews × rating + 10 × Texas mean) ÷ (reviews + 10)`, open and reviewed studios only. Article, ItemList, FAQPage schema |
| `/tools/` | Free tools hub |
| `/tools/<tool>/` | Image Background Remover, Image Resizer, Image Compressor, Image Cropper, Image Format Converter. All run in the browser (`assets/tools/`); nothing is uploaded |
| `/about/` | About and contact |
| `/llms.txt` | Site summary for AI crawlers |
| `/api/geo` | Vercel function (`api/geo.js`) that returns the visitor's approximate city and coordinates from Vercel IP-geolocation headers. `assets/home-geo.js` uses it to show "Top studios near <City>" on the homepage. `/?near=<city-slug>` forces a city for testing |
| `/sitemap/` | HTML sitemap |
| `/sitemap.xml` | XML sitemap |
| `/robots.txt` | Robots file |

The homepage hero photograph is *Photographic studio* by [Alexander Dummer](https://unsplash.com/photos/aS4Duj2j7r4), published on Unsplash on 16 August 2016 and released under [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). Source files and the credit live in `assets/hero/`.

City hubs link to every studio in that city, to nearby cities (by the average coordinates of listings in each city), back to `/` and `/tx/`, and to both services. Studio pages use the breadcrumb Home → Texas → City → Studio, with `BreadcrumbList` schema. Studio pages include `LocalBusiness` schema. Titles, descriptions, and canonical tags are unique.

## Set the payment link

Edit **`config/site.json`**. This is the only place the payment URL is defined:

```json
"STRIPE_PAYMENT_LINK": "https://buy.stripe.com/your-editing-link",
"STRIPE_PAYMENT_LINK_ENHANCE": "https://buy.stripe.com/your-enhancement-link"
```

Leave a key as `""` until that Stripe Payment Link exists. A value that starts with `https://` becomes the Order Now button on that service page. Anything else keeps the button on the order form, which includes a service selector.

Also in that file:

- `ORDER_FORM_ENDPOINT` — optional `https://` URL that receives the order form as a normal POST (`name`, `email`, `instructions`, and `service`). Leave empty to open a `mailto:` to `CONTACT_EMAIL`.
- `CONTACT_EMAIL` — address used for the mailto fallback. The form does not upload files; the page asks the customer to paste a share link or attach images in their email app.

Rebuild after changing the file:

```bash
python3 scripts/build.py
```

That regenerates `dist/assets/site-config.js` from the same keys. To add another service later, append an object to `config/services.json` and rebuild. The main nav links to `/services/`, which lists every entry.

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
assets/directory.css      studio card chips, filter bar, studio page sections
assets/directory.js       open-now status, hours highlight, city filter bar
assets/city-images/       generated 1200x630 featured image per city
data/website-enrichment.json  public homepage info per studio (title, description, socials)
assets/brand/             logo, favicons, manifest, social image
scripts/clean_data.py
scripts/enrich_websites.py reads each studio's own homepage (aiohttp, bs4; local only)
scripts/studio_info.py     hours parsing, specialties, features, summaries
scripts/directory_pages.py studio, city hub, and specialty pages
scripts/render_city_images.py  Pillow city images (local only)
scripts/build.py
scripts/check_links.py
scripts/render_brand.py
vercel.json               build command and dist output
```

## Listing data on each page

- Hours, rating breakdown, amenities (Google "about" attributes), booking link, photos count, verified flag, neighborhood, and time zone come straight from the export.
- Specialties are inferred from Google listing categories, the business name, topics customers mention, the booking link, and the studio's own homepage text. Pages label them "based on listing details". Nothing is added when no field supports it.
- The export has no review text, only the rating, count, per-star counts, and a few review topics. Pages link to Google for the actual reviews.
- Specialty pages (`/tx/<city>/<specialty>/`) exist only where 3 or more studios in a city share the specialty and the specialty is not every studio in the city.
- Refresh website info with `python3 scripts/enrich_websites.py` (use `--refresh` to refetch all), then `python3 scripts/clean_data.py`, `python3 scripts/render_city_images.py` if cities changed, and `python3 scripts/build.py`.

`dist/` is gitignored. Vercel creates it on deploy.

## Forms, uploads and analytics

- Order, contact and claim/removal forms post to `api/submit.js`, which emails the owner through Resend. Vercel env vars: `RESEND_API_KEY` (sending-only key), `FORM_TO_EMAIL`, `FORM_FROM_EMAIL` (must be on a Resend-verified domain).
- Customer photos upload straight to Vercel Blob through `api/upload.js` (25 MB each, up to 12 files). Env var: `BLOB_READ_WRITE_TOKEN`. The browser uploader is bundled with `npm run bundle:upload` into `assets/blob-upload.js`.
- Vercel Web Analytics is enabled for the project; the script is `/_vercel/insights/script.js`.
