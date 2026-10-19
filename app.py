import asyncio
import time

import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import sites

app = FastAPI()
CACHE_TTL = 30 * 60
_cache = {}  # amazon url -> (time, response)  ponytail: in-memory, lost on restart; fine for a demo


class Ask(BaseModel):
    url: str


async def check(client, platform, spec):
    try:
        status, hit = await sites.ADAPTERS[platform](client, spec)
    except Exception as e:  # a blocked/broken site must not look like "not listed"
        return {"platform": platform, "status": "error", "note": f"Couldn't check right now ({type(e).__name__})."}
    out = {"platform": platform, "status": status}
    if hit:
        out.update(title=hit["title"], url=hit["url"], price=hit.get("price"), colour=hit.get("colour"))
    return out


@app.post("/api/compare")
async def compare(ask: Ask):
    url = ask.url.strip()
    if url in _cache and time.time() - _cache[url][0] < CACHE_TTL:
        return _cache[url][1]
    async with httpx.AsyncClient(headers=sites.HEADERS, follow_redirects=True, timeout=25) as client:
        try:
            spec = await sites.amazon(client, url)
        except sites.NotSupported as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        except httpx.HTTPError as e:
            return JSONResponse({"error": f"Couldn't load the Amazon page ({type(e).__name__})."}, status_code=502)
        results = await asyncio.gather(*(check(client, p, spec) for p in sites.PLATFORMS[spec["category"]]))
    product = {k: spec[k] for k in ("title", "category", "brand", "ram", "storage", "screen", "colour", "url")}
    resp = {"product": product, "results": results}
    if all(r["status"] != "error" for r in results):
        _cache[url] = (time.time(), resp)
    return resp


@app.get("/")
def index():
    return FileResponse("index.html")


@app.get("/debug")
async def debug():
    # Temporary: what Render sees on a Flipkart product page and a Croma product page.
    out = {}
    async with httpx.AsyncClient(headers=sites.HEADERS, follow_redirects=True, timeout=25) as c:
        r = await c.get("https://www.flipkart.com/nike-court-royale-tennis-shoes-men/p/itmf3xwjxnwwbqpk?pid=SHOHMSQJXCFPGFQF")
        out["flipkart_page"] = {"status": r.status_code, "bytes": len(r.text)}
        html = (await sites.get(c, "https://www.croma.com/samsung-galaxy-s24-5g-8gb-ram-128gb-cobalt-violet-/p/303832", {})).text
        low = html.lower()
        out["croma"] = {
            "bytes": len(html),
            "ldjson": [b[:400] for b in __import__("re").findall(r'application/ld\+json[^>]*>(.*?)</script>', html, 16)][:4],
            "words": {w: low.count(w) for w in ["instock", "outofstock", "out of stock", "notify me", "add to cart", "buy now", "sold out", "currently unavailable", "availability"]},
            "around": [html[max(0, i - 120): i + 120] for i in [low.find("availability"), low.find("price")] if i >= 0],
        }
    return out
