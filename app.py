import asyncio
import os
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI

app = FastAPI()

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
    "Accept-Language": "en-IN,en;q=0.9",
}

# (url, text that only appears when real results come back)
PROBES = {
    "amazon": ("https://www.amazon.in/s?k=samsung+galaxy+s24", "galaxy s24"),
    "flipkart": ("https://www.flipkart.com/search?q=samsung+galaxy+s24", "galaxy s24"),
    "croma": ("https://www.croma.com/searchB?q=samsung%20galaxy%20s24", "galaxy s24"),
    "myntra": ("https://www.myntra.com/nike-shoes", "nike"),
    "croma_api": ("https://api.croma.com/searchservices/v1/search?currentPage=0"
                  "&query=samsung%20galaxy%20s24&fields=FULL", "galaxy s24"),
    "myntra_api": ("https://www.myntra.com/gateway/v4/search/nike-shoes"
                   "?rawQuery=nike%20shoes&rows=5&o=0", "nike"),
}

# Sites that block datacenter IPs go through ScraperAPI (residential IPs, India).
# Extra params per site: render=true runs a real browser, premium=true uses
# residential IPs for protected domains. Both cost more credits.
PROXIED = {"croma": {"render": "true"}, "myntra": {}, "croma_api": {"premium": "true"}}


def via_proxy(url, extra):
    q = {"api_key": os.environ["SCRAPER_API_KEY"], "url": url, "country_code": "in", **extra}
    return "https://api.scraperapi.com/?" + urlencode(q)


# Myntra's gateway API wants the session cookies its homepage sets.
MYNTRA_API_HEADERS = {"Accept": "application/json", "x-meta-app": "channel=web",
                      "x-myntraweb": "Yes", "Referer": "https://www.myntra.com/nike-shoes"}


async def probe(client, name, url, marker):
    try:
        if name == "myntra_api":
            await client.get("https://www.myntra.com/")
            r = await client.get(url, headers=MYNTRA_API_HEADERS)
        elif name in PROXIED and os.environ.get("SCRAPER_API_KEY"):
            r = await client.get(via_proxy(url, PROXIED[name]), timeout=70)
        else:
            r = await client.get(url)
        ok = r.status_code < 400 and marker in r.text.lower()
        out = {"status": r.status_code, "bytes": len(r.text), "got_results": ok}
        if r.status_code >= 400:
            out["body"] = r.text[:200]
        return name, out
    except Exception as e:
        return name, {"error": repr(e)}


@app.get("/probe")
async def probe_all():
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as c:
        return dict(await asyncio.gather(*(probe(c, n, *p) for n, p in PROBES.items())))


@app.get("/")
def root():
    return {"ok": True, "try": "/probe", "scraper_key_set": bool(os.environ.get("SCRAPER_API_KEY"))}
