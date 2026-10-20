"""Fetch and parse Amazon (source) and Flipkart / Myntra / Croma (targets) into plain dicts."""
import asyncio
import gzip
import json
import os
import re
import time
from urllib.parse import quote, urlencode

import httpx
from selectolax.lexbor import LexborHTMLParser

import match

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ponytail: free ScraperAPI plan allows 1 concurrent request; raise if plan upgrades.
PROXY_SLOT = asyncio.Semaphore(1)


class NotSupported(Exception):
    """Shown to the user as-is."""


async def get(client, url, proxy=None):
    """proxy=None fetches directly; a dict sends it through ScraperAPI with those extra params."""
    if proxy is None:
        r = await client.get(url)
    else:
        q = {"api_key": os.environ["SCRAPER_API_KEY"], "url": url, "country_code": "in", **proxy}
        async with PROXY_SLOT:
            r = await client.get("https://api.scraperapi.com/?" + urlencode(q), timeout=70)
    r.raise_for_status()
    return r


def clean(s):
    return re.sub(r"[\s\u200e\u200f]+", " ", s or "").strip()


# ---------- Amazon ----------

CATEGORIES = [  # (category, words in Amazon breadcrumbs, fallback words in title)
    ("phone", ("smartphones",), ("smartphone", "mobile phone", "iphone")),  # iPhone pages often lack breadcrumbs
    ("tv", ("televisions",), (" tv", "television")),
    ("tshirt", ("t-shirts", "polos", "jerseys", "tees"), ("t-shirt", "tshirt", "polo", "jersey")),
    ("sneakers", ("shoes",), ("shoe", "sneaker")),
]


async def amazon(client, url):
    if not re.search(r"amazon\.in|amzn\.", url):
        raise NotSupported("That doesn't look like an amazon.in link.")
    m = re.search(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})", url)
    if not m:  # short link like amzn.in/d/xyz: follow it
        m = re.search(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})", str((await client.get(url)).url))
    if not m:
        raise NotSupported("Couldn't find a product ID in that link.")
    page = f"https://www.amazon.in/dp/{m.group(1)}"
    html = (await get(client, page)).text
    if 'id="productTitle"' not in html and os.environ.get("SCRAPER_API_KEY"):
        html = (await get(client, page, {})).text  # Amazon showed a bot check; retry via proxy
    if 'id="productTitle"' not in html:
        raise NotSupported("Amazon didn't return the product page (bot check). Try again in a minute.")
    return parse_amazon(html, page)


def parse_amazon(html, url):
    t = LexborHTMLParser(html)
    for s in t.css("script, style"):
        s.decompose()

    def text(sel):
        n = t.css_first(sel)
        return clean(n.text()) if n else ""

    title = text("#productTitle")
    crumbs = text("#wayfinding-breadcrumbs_feature_div").lower()
    fields = {}
    for tr in t.css("#productOverview_feature_div tr, #productDetails_techSpec_section_1 tr, "
                    "#productDetails_detailBullets_sections1 tr, #prodDetails tr"):  # last: newer layout
        cells = tr.css("th, td")
        if len(cells) >= 2:
            fields.setdefault(clean(cells[0].text()).lower(), clean(cells[1].text()))
    for li in t.css("#detailBullets_feature_div li, #productFactsDesktopExpander li"):
        k, _, v = clean(li.text()).partition(":")
        if v:
            fields.setdefault(k.strip().lower(), v.strip())

    category = next((c for c, cw, _ in CATEGORIES if any(w in crumbs for w in cw)), None)
    if not category and not crumbs:
        low = " " + title.lower()
        category = next((c for c, _, tw in CATEGORIES if any(w in low for w in tw)), None)
    if not category:
        raise NotSupported("This product isn't a smartphone, TV, sneaker or T-shirt/polo/jersey.")

    byline = text("#bylineInfo")
    bm = re.search(r"Visit the (.+?) Store|Brand: (.+)", byline)
    brand = fields.get("brand") or (bm and (bm.group(1) or bm.group(2))) or title.split()[0]
    brand_words = set(match.tokens(brand)) | {match.norm(brand)}

    groups = re.findall(r"\(([^)]*)\)", title)
    paren = " ".join(groups)
    sizes = sorted(filter(None, (match.gb(x) for x in re.findall(r"\d+\s*[GT]B", paren, re.I))))
    ram = match.gb(fields.get("ram memory installed size") or fields.get("ram")) \
        or match.gb((re.search(r"\d+\s*GB\s*RAM", title, re.I) or [""])[0]) or (sizes[0] if len(sizes) > 1 else None)
    storage = match.gb(fields.get("memory storage capacity") or fields.get("internal storage")) \
        or (sizes[-1] if sizes else None)
    if category == "phone" and (not storage or storage < 32):  # Amazon sometimes fills storage with the RAM size
        std = re.findall(r"\b(32|64|128|256|512)\b|\b(1)\s*TB\b", title, re.I)  # "(Amazonite, 12, GB, 256)"
        storage = max((1024 if t else int(g)) for g, t in std) if std else storage
    if ram and (ram > 32 or (storage and ram >= storage)):  # ... and RAM with the storage size
        ram = None
    sm = re.search(r"(\d+(?:\.\d+)?)\s*inch", fields.get("screen size", "") + " " + title, re.I)
    screen = float(sm.group(1)) if sm else None

    colour = text("#inline-twister-expanded-dimension-text-color_name") or fields.get("colour") \
        or fields.get("color") or fields.get("brand color") or (groups[-1].split(",")[0] if groups else "")
    canon = t.css_first('link[rel="canonical"]')
    slug = re.sub(r".*amazon\.in/([^/]+)/dp/.*", r"\1", canon.attributes.get("href", "")) if canon else ""
    if "/" in slug:
        slug = ""
    if not match.colour_family(colour):  # "(163cm)" isn't a colour; "PUTBEI/LINGRN" is a code: the link says "Beige"
        page = text("title")  # "Buy Adidas Men Soulzie M, Casual Shoe, Beige, 9 at Amazon.in"
        named = [w for w in re.findall(r"[a-z]+", " ".join((slug, page, title)).lower()) if w in match.COLOURS]
        colour = named[0].title() if named else ""

    if category in ("phone", "tv"):
        name = re.split(r"[|:,]|\bwith\b", re.sub(r"\([^)]*\)", " ", title))[0]  # "iPhone 17e 256 GB: 15.40 cm..."
        # A TV's model number is how other sites name it; a phone's is a regional part number (MYED3HN/A) nobody shows.
        code = (fields.get("item model number") or fields.get("model number") or "") if category == "tv" else ""
        toks = match.tokens(name + " " + code, drop=brand_words)
    else:
        # Nike-style article codes in the link ("Court-Royale-Running-749747-107") aren't on other sites' titles.
        slug = re.sub(r"\b\d{5,}(-\d{1,3}){0,2}\b", " ", slug)  # "749747-107" and a size after it: "749747-107-10"
        toks = match.tokens(fields.get("model name", "") + " " + slug.replace("-", " "), drop=brand_words) \
            or match.tokens(title, drop=brand_words)
        # The link can drop the version ("ASICS-Gel-Excite-Black-Running-Shoes" for Gel-Excite 10): take it from the title.
        toks += [w for w in match.tokens(title, drop=brand_words) if w.isdigit() and w not in toks]

    spec = {
        "url": url, "title": title, "category": category, "brand": brand, "tokens": toks,
        "ram": ram, "storage": storage, "screen": screen, "colour": colour,
        "colour_family": match.colour_family(colour),
        "gender": match.gender(title + " " + fields.get("department", "")),
    }
    spec["queries"] = queries(spec)
    return spec


def queries(spec):
    """Search texts to try in order: specific first, then looser."""
    b, words = spec["brand"], [t for t in spec["tokens"] if not match.is_code(t) or spec["category"] == "phone"]
    cat = spec["category"]
    if cat == "phone":
        ram = f"{spec['ram']}gb ram " if spec["ram"] else ""
        return [f"{b} {' '.join(spec['tokens'])} {ram}{spec['storage'] or ''}gb", f"{b} {' '.join(spec['tokens'])}"]
    if cat == "tv":
        size = f"{spec['screen']:g} inch " if spec["screen"] else ""
        codes = [t for t in spec["tokens"] if match.is_code(t)]
        return [f"{b} {' '.join(words)} {size}tv"] + [f"{b} {c}" for c in codes[:1]]
    noun = "shoes" if cat == "sneakers" else ("polo" if "polo" in spec["title"].lower() else "tshirt")
    g = spec["gender"] if spec["gender"] in ("men", "women") else ""
    return [f"{b} {' '.join(spec['tokens'])} {g} {noun}".replace("  ", " "), f"{b} {' '.join(spec['tokens'])}"]


# ---------- Flipkart (direct) ----------

def _walk(o, key):
    if isinstance(o, dict):
        if key in o:
            yield o[key]
        for v in o.values():
            yield from _walk(v, key)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v, key)


def parse_flipkart(html, brand):
    m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*</script>", html, re.S)
    if not m:
        raise RuntimeError("Flipkart page had no product data")
    out, seen = [], set()
    for info in _walk(json.loads(m.group(1)), "productInfo"):
        v = info.get("value") if isinstance(info, dict) else None
        if not v or "titles" not in v or v.get("id") in seen:
            continue
        seen.add(v.get("id"))
        ti = v["titles"]
        title = ti.get("title") or ""
        specs = " | ".join(v.get("keySpecs") or [])
        blob = f"{title} | {ti.get('subtitle', '')} | {specs}"
        model_id = (re.search(r"Model ID:\s*(\S+)", specs) or [None, ""])[1]
        cm = re.search(r"Colou?r:\s*([^|]+)", specs)
        paren = re.findall(r"\(([^)]*)\)", title)
        colour = cm.group(1) if cm else (ti.get("subtitle", "").split(",")[0] if "," in ti.get("subtitle", "") else
                                         (paren[-1].split(",")[0] if paren else ""))
        colour = colour.strip() if match.colour_family(colour) else ""  # "(55 inch) ... (4K)" isn't a colour
        rm = re.search(r"(\d+)\s*GB RAM", blob, re.I)
        sm = re.search(r"(\d+)\s*(GB|TB) ROM", blob, re.I) or re.search(r",\s*(\d+)\s*(GB|TB)\)", title)
        scr = re.search(r"\((\d+(?:\.\d+)?)\s*inch\)", title)
        prices = [p["value"] for p in (v.get("pricing") or {}).get("prices", []) if not p.get("strikeOff")]
        out.append({
            "title": title, "brand": v.get("productBrand") or ti.get("superTitle"),
            "url": "https://www.flipkart.com" + v.get("baseUrl", ""),
            "tokens": match.tokens(title + " " + model_id, drop={match.norm(brand)}),
            "ram": int(rm.group(1)) if rm else None,
            "storage": match.gb(sm.group(0)) if sm else None,
            "screen": float(scr.group(1)) if scr else None,
            "colour": colour.strip(), "colour_family": match.colour_family(colour),
            "gender": match.gender(title),
            "stock": "in" if (v.get("availability") or {}).get("displayState") == "IN_STOCK" else "out",
            "price": prices[0] if prices else None,
        })
    return out


def flipkart_page_stock(html):
    low = html.lower()
    if any(w in low for w in ("sold out", "currently unavailable", "coming soon")):
        return "out"
    return "in" if ("add to cart" in low or "buy now" in low) else "out"


async def flipkart_page(client, url):
    """Product page HTML. Flipkart rate-limits Render's IP (429) on product pages, so fall back to the proxy;
    None if both fail (the search result's stock is kept)."""
    try:
        return (await get(client, url)).text
    except Exception:
        pass
    if os.environ.get("SCRAPER_API_KEY"):
        try:
            return (await get(client, url, {})).text
        except Exception:
            pass
    return None


FULL_PAGE = 20  # fewer results than this on page 1 = there is no page 2 worth fetching


def search_pages(queries):
    """(query, page) to try: page 2 of the best query only, since it's the one that should find the product."""
    return [(q, p) for i, q in enumerate(queries) for p in ((1, 2) if i == 0 else (1,))]


async def search_page(client, url, proxy, page):
    """Page 1 must load (a failure is an error, not 'not listed'); page 2 is a bonus, so a failure there is skipped."""
    try:
        return (await get(client, url, proxy)).text
    except httpx.HTTPError:
        if page == 1:
            raise
        return None


async def flipkart(client, spec):
    last, seen = None, []
    for q, page in search_pages(spec["queries"]):
        if page == 2 and last < FULL_PAGE:
            continue
        html = await search_page(client, f"https://www.flipkart.com/search?q={quote(q)}&page={page}", None, page)
        if html is None:
            continue
        found = parse_flipkart(html, spec["brand"])
        last = len(found)
        seen += found
        hits = match.rank(spec, found)
        if hits:
            # Search cards show stock for one size only, so "out" there isn't final: confirm on the page.
            if not any(c["stock"] == "in" for c in hits):
                for c in hits[:2]:
                    html = await flipkart_page(client, c["url"])
                    if html:
                        c["stock"] = flipkart_page_stock(html)
            return match.decide(hits)
    return match.decide([], match.miss_note(spec, seen))


# ---------- Myntra (via proxy: blocks datacenter IPs) ----------

def parse_myntra(html, brand):
    m = re.search(r"window\.__myx\s*=\s*(\{.*?\})\s*</script>", html, re.S)
    if not m:
        raise RuntimeError("Myntra page had no product data (blocked?)")
    products = ((json.loads(m.group(1)).get("searchData") or {}).get("results") or {}).get("products") or []
    return [{
        "title": p.get("productName", ""), "brand": p.get("brand"),
        "url": "https://www.myntra.com/" + p.get("landingPageUrl", ""),
        "tokens": match.tokens(p.get("productName", ""), drop={match.norm(brand)}),
        "colour": p.get("primaryColour"), "colour_family": match.colour_family(p.get("primaryColour")),
        "gender": match.gender(p.get("gender")),
        "stock": "in" if any(i.get("available") for i in p.get("inventoryInfo") or []) else "out",
        "price": p.get("price"),
    } for p in products]


async def myntra(client, spec):
    last, seen = None, []
    for q, page in search_pages(spec["queries"]):
        if page == 2 and last < FULL_PAGE:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")
        html = await search_page(client, f"https://www.myntra.com/{slug}?rawQuery={quote(q)}&p={page}", {}, page)
        if html is None:
            continue
        found = parse_myntra(html, spec["brand"])
        last = len(found)
        seen += found
        hits = match.rank(spec, found)
        if hits:
            return match.decide(hits)
    return match.decide([], match.miss_note(spec, seen))


# ---------- Croma (sitemap for lookup, proxied product page for stock) ----------

# Croma's sitemap index links these with a missing slash ("/sitemapsphones-..."); these paths work.
CROMA_SITEMAPS = {"phone": "sitemaps/phones-wearables/c/1.gz", "tv": "sitemaps/televisions-accessories/c/997.gz"}
CROMA_TTL = 3600  # Croma list refresh; stock and price are fetched live per search
_croma = {}  # category -> (loaded_at, [urls])
_croma_lock = asyncio.Lock()


def croma_product_urls(xml):
    """Product links from a sitemap. IDs are numbers (/p/303832) or codes (/p/ph120101qn80h_samsung_797, even with spaces)."""
    return [u.replace(" ", "%20") for u in re.findall(r"<loc>([^<]*/p/[^<]+)</loc>", xml)]


async def croma_urls(client, category):
    async with _croma_lock:
        at, urls = _croma.get(category, (0, []))
        if time.time() - at > CROMA_TTL:
            body = (await get(client, "https://www.croma.com/" + CROMA_SITEMAPS[category], {})).content
            if body[:2] == b"\x1f\x8b":
                body = gzip.decompress(body)
            urls = croma_product_urls(body.decode("utf-8", "replace"))
            if not urls:
                raise RuntimeError("Croma sitemap came back empty")
            _croma[category] = (time.time(), urls)
        return urls


def croma_candidate(url, brand):
    text = url.rsplit("/p/", 1)[0].rsplit("/", 1)[-1].replace("-", " ")
    rm = re.search(r"(\d+)\s?gb ram", text)
    sm = re.search(r"(\d+)\s?(gb|tb)\b(?! ram)", text)
    scr = re.search(r"(\d+(?:\.\d+)?) inch", text)
    return {"title": text.title(), "url": url, "tokens": match.tokens(text, drop={match.norm(brand)}),
            "ram": int(rm.group(1)) if rm else None, "storage": match.gb(sm.group(0)) if sm else None,
            "screen": float(scr.group(1)) if scr else None,
            "colour_family": match.colour_family(text)}  # link ends in the colour: picks the same-colour listing


def croma_price(html):
    """Selling price from the page's app state; some loads leave that empty, so fall back to the schema.org offer."""
    m = re.search(r'"sellingPrice":\{"value":"?([\d.]+)', html) \
        or re.search(r'"offers"\s*:\s*\{[^}]*?"price"\s*:\s*"?([\d.]+)', html)
    return float(m.group(1)) if m else None


CROMA_NOTE = "Listed on Croma. Stock isn't checked live: Croma only reveals it to a real browser."


async def croma(client, spec):
    """Croma's page never says whether it's in stock (its own scripts ask a blocked API), so a listed
    product whose page still loads counts as in stock. A delisted product's page 404s -> try the next."""
    cands = [croma_candidate(u, spec["brand"]) for u in await croma_urls(client, spec["category"])]
    for c in match.rank(spec, cands)[:2]:  # ponytail: at most 2 page loads (1 credit each)
        try:
            html = (await get(client, c["url"], {})).text
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (404, 410):
                continue
            raise
        c.update(stock="in", price=croma_price(html), note=CROMA_NOTE)
        return match.decide([c])
    return match.decide([], match.miss_note(spec, cands))


ADAPTERS = {"flipkart": flipkart, "myntra": myntra, "croma": croma}
PLATFORMS = {"phone": ("flipkart", "croma"), "tv": ("flipkart", "croma"),
             "sneakers": ("flipkart", "myntra"), "tshirt": ("flipkart", "myntra")}
