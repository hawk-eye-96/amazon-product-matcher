# Amazon Product Matcher

Paste an Amazon.in product link and see whether the **same product** is sold on Flipkart, Croma or Myntra.

**Live demo:** https://amazon-product-matcher.onrender.com
(free hosting: if nobody has used it for a while, the first load takes about a minute while the server wakes up)

**How the matching works, in plain words:** [HOW_MATCHING_WORKS.md](HOW_MATCHING_WORKS.md)

## What it does

| Category | Platforms checked | Must match (besides brand + model) |
|---|---|---|
| Smartphones | Flipkart, Croma | RAM and storage |
| TVs | Flipkart, Croma | Screen size |
| Sneakers | Flipkart, Myntra | Colour |
| T-shirts, polos, jerseys | Flipkart, Myntra | Colour |

Each platform shows one of three states, each styled differently:

- **In stock**: the same product, buyable, with a link
- **Out of stock**: the same product, not buyable right now, with a link
- **Not listed**: not sold there. When the model exists in another variant, it says which and links to it
  ("Found this model, but only with 16 GB RAM / 512 GB").

A site that fails or blocks the request shows **Couldn't check** rather than a false "Not listed".
Other products (accessories, headphones, kurtas, formal shoes…) are rejected with a message.
Short links (`amzn.in/d/…`) work.

## How it works

```
Amazon page ──► product spec ──► search each platform ──► score every listing ──► best match + stock
               (brand, model,     (specific query first,    (brand, model words/
                RAM, size,         then a looser one)        codes, category rule)
                colour)
```

1. **Read Amazon** (`sites.py: parse_amazon`): title, brand, breadcrumb (gives the category), spec table, colour.
   The title is cleaned into *model words*: marketing words (AI, Smart, 5G, Premium…) are dropped,
   model codes like `UA55U8400FULXL` are kept whole.
2. **Search** each platform:
   - **Flipkart:** search page JSON.
   - **Myntra:** search page JSON, through a proxy, because Myntra blocks datacenter IPs.
   - **Croma:** Croma blocks bots, so the app uses Croma's product sitemap (cached for an hour) to find listings.
3. **Score** each listing (`match.py: score`). It is rejected unless the brand matches and the model matches:
   - the same full model code, or
   - the same variant words (Pro / Plus / FE / Ultra…), the same numbers (iPhone 15 ≠ 16), and enough shared model words.

   The category rule (RAM + storage, screen size ±1", or colour family + gender) must hold too.
4. **Decide** (`match.decide`): it prefers an in-stock match. Flipkart search cards show stock for one size only,
   so an "out" there is confirmed on the product page.

When Amazon's title names no model ("Levi's Men T-Shirt, Green"), the app says it can't be matched reliably
instead of guessing.

## Run it locally

```bash
pip install -r requirements.txt
export SCRAPER_API_KEY=...   # optional: ScraperAPI key, needed for Myntra and Croma
uvicorn app:app --port 7860
# open http://localhost:7860
```

Tests (no network needed):

```bash
python3 test_match.py && python3 test_sites.py
```

Deploys as a Docker web service (see `Dockerfile`). It's hosted on Render's free tier with `SCRAPER_API_KEY` set as an
environment variable.

## Files

| File | What's in it |
|---|---|
| `app.py` | FastAPI server: `POST /api/compare`, serves the page, 30-minute result cache |
| `sites.py` | Fetching and parsing Amazon, Flipkart, Myntra, Croma |
| `match.py` | Model words, colour families, scoring, "found only in…" notes |
| `index.html` | The whole UI (no build step) |
| `test_*.py` | Good, bad and edge cases, many taken from real mismatches |

## Testing

Besides the unit tests, it was tested by hand in a browser on 120+ real Amazon products across the 4 categories
(and unsupported ones):

- open the Amazon product, paste the link in the app, then open every returned link;
- check the model, RAM/storage, size or colour on the other site, and compare product photos for fashion;
- for "Not listed", search the other site by hand.

Every mismatch found became a fix plus a test.

## Known limitations

- **Croma:** live stock and today's price only render in a real browser, so Croma shows its listed price, and the card says so.
- **Stock is per product, not per size.**
- **Fashion items without a model name** (most plain tees) show "can't be matched reliably" on purpose.
- **Colours:** Flipkart search cards sometimes give only the main colour ("White" for a white/black shoe), and Myntra
  can hide other colours behind "More colors".
- **Hosting:** free hosting sleeps when idle. Results are cached in memory for 30 minutes, keyed by the exact link.
