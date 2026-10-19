import asyncio

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
}


async def probe(client, name, url, marker):
    try:
        r = await client.get(url)
        ok = r.status_code < 400 and marker in r.text.lower()
        return name, {"status": r.status_code, "bytes": len(r.text), "got_results": ok}
    except Exception as e:
        return name, {"error": repr(e)}


@app.get("/probe")
async def probe_all():
    async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as c:
        return dict(await asyncio.gather(*(probe(c, n, *p) for n, p in PROBES.items())))


@app.get("/")
def root():
    return {"ok": True, "try": "/probe"}
